from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import (
    FastAPI,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError as PydanticValidationError

from .config import Settings, get_settings
from .events import EventBroker, RoomHub
from .fal_gateway import build_generation_gateway
from .models import (
    CartCreate,
    CartItemRequest,
    CheckoutCreate,
    FalWebhookPayload,
    PollCreate,
    ProductPinRequest,
    SegmentAirRequest,
    SegmentGenerateRequest,
    SessionCreate,
    SessionState,
    VoteRequest,
)
from .seed import seed_products
from .services import GenerationService
from .store import ConflictError, NotFoundError, Store, ValidationError
from .webhook_verifier import FalWebhookVerifier, WebhookVerificationError

logger = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).parent / "static"


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        store = Store(resolved_settings.resolved_database_path)
        store.initialize()
        if resolved_settings.auto_seed_products:
            seed_products(store)
        hub = RoomHub()
        broker = EventBroker(store, hub)
        gateway = build_generation_gateway(resolved_settings)
        generation = GenerationService(
            store=store,
            broker=broker,
            gateway=gateway,
            settings=resolved_settings,
        )
        verifier = FalWebhookVerifier(
            jwks_url=resolved_settings.fal_jwks_url,
            enabled=(
                resolved_settings.fal_mode == "queue"
                and resolved_settings.fal_verify_webhooks
            ),
        )
        app.state.settings = resolved_settings
        app.state.store = store
        app.state.hub = hub
        app.state.broker = broker
        app.state.generation = generation
        app.state.verifier = verifier
        try:
            yield
        finally:
            await generation.close()
            store.close()

    app = FastAPI(
        title="Live House — AI Live Commerce",
        version="0.1.0",
        description="Live House vertical slice for live sessions, realtime interaction, commerce, and fal-powered generation.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"] ,
        allow_headers=["*"],
    )
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.exception_handler(NotFoundError)
    async def handle_not_found(_: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ConflictError)
    async def handle_conflict(_: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(ValidationError)
    async def handle_validation(_: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(PydanticValidationError)
    async def handle_internal_model_validation(
        _: Request, exc: PydanticValidationError
    ) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": exc.errors()})

    def store_from(request: Request) -> Store:
        return request.app.state.store

    def broker_from(request: Request) -> EventBroker:
        return request.app.state.broker

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/viewer", include_in_schema=False)
    async def viewer() -> FileResponse:
        return FileResponse(STATIC_DIR / "viewer.html")

    @app.get("/studio", include_in_schema=False)
    async def studio() -> FileResponse:
        return FileResponse(STATIC_DIR / "studio.html")

    @app.get("/architecture", include_in_schema=False)
    async def architecture() -> FileResponse:
        return FileResponse(STATIC_DIR / "architecture.html")

    @app.get("/health")
    async def health(request: Request) -> dict[str, Any]:
        return {
            "status": "ok",
            "environment": request.app.state.settings.app_env,
            "fal_mode": request.app.state.settings.fal_mode,
        }

    @app.post("/v1/demo/bootstrap")
    async def demo_bootstrap(request: Request) -> dict[str, Any]:
        store = store_from(request)
        seed_products(store)
        session = store.create_session(
            SessionCreate(
                title="Live House Demo",
                playback_url="/static/demo-program.mp4",
            )
        )
        event = await broker_from(request).publish(
            session["id"], "live.session.created", {"session": session}
        )
        return {
            "session": store.get_session(session["id"]),
            "products": store.list_products(),
            "created_event": event,
            "viewer_url": f"/viewer?session_id={session['id']}",
            "studio_url": f"/studio?session_id={session['id']}",
        }

    @app.post("/v1/live-sessions", status_code=status.HTTP_201_CREATED)
    async def create_session(payload: SessionCreate, request: Request) -> dict[str, Any]:
        store = store_from(request)
        session = store.create_session(payload)
        await broker_from(request).publish(
            session["id"], "live.session.created", {"session": session}
        )
        return store.get_session(session["id"])

    @app.get("/v1/live-sessions")
    async def list_sessions(request: Request) -> list[dict[str, Any]]:
        return store_from(request).list_sessions()

    @app.get("/v1/live-sessions/{session_id}")
    async def get_session(session_id: str, request: Request) -> dict[str, Any]:
        return store_from(request).get_session(session_id)

    @app.get("/v1/live-sessions/{session_id}/snapshot")
    async def get_snapshot(
        session_id: str,
        request: Request,
        after_sequence: int = Query(default=0, ge=0),
    ) -> dict[str, Any]:
        settings_: Settings = request.app.state.settings
        return store_from(request).snapshot(
            session_id,
            after_sequence=after_sequence,
            replay_limit=settings_.event_replay_limit,
        )

    @app.post("/v1/live-sessions/{session_id}:start")
    async def start_session(session_id: str, request: Request) -> dict[str, Any]:
        store = store_from(request)
        session = store.set_session_state(session_id, SessionState.LIVE)
        await broker_from(request).publish(
            session_id,
            "live.session.started",
            {"session": session},
            program_time_ms=0,
        )
        return store.get_session(session_id)

    @app.post("/v1/live-sessions/{session_id}:end")
    async def end_session(session_id: str, request: Request) -> dict[str, Any]:
        store = store_from(request)
        session = store.set_session_state(session_id, SessionState.ENDED)
        await broker_from(request).publish(
            session_id,
            "live.session.ended",
            {"session": session},
            program_time_ms=store.current_program_time_ms(session_id),
        )
        return store.get_session(session_id)

    @app.get("/v1/products")
    async def list_products(request: Request) -> list[dict[str, Any]]:
        return store_from(request).list_products()

    @app.post("/v1/live-sessions/{session_id}/products/{sku}:pin")
    async def pin_product(
        session_id: str, sku: str, payload: ProductPinRequest, request: Request
    ) -> dict[str, Any]:
        store = store_from(request)
        session = store.pin_product(session_id, sku)
        product = store.get_product(sku)
        program_time_ms = (
            payload.program_time_ms
            if payload.program_time_ms is not None
            else store.current_program_time_ms(session_id)
        )
        event = await broker_from(request).publish(
            session_id,
            "product.pinned",
            {"product": product},
            program_time_ms=program_time_ms,
            correlation_id=sku,
        )
        return {"session": session, "product": product, "event": event}

    @app.post("/v1/live-sessions/{session_id}/products:unpin")
    async def unpin_product(session_id: str, request: Request) -> dict[str, Any]:
        store = store_from(request)
        session = store.pin_product(session_id, None)
        event = await broker_from(request).publish(
            session_id,
            "product.unpinned",
            {},
            program_time_ms=store.current_program_time_ms(session_id),
        )
        return {"session": session, "event": event}

    @app.post("/v1/live-sessions/{session_id}/polls", status_code=201)
    async def create_poll(
        session_id: str, payload: PollCreate, request: Request
    ) -> dict[str, Any]:
        poll = store_from(request).create_poll(session_id, payload)
        await broker_from(request).publish(
            session_id, "poll.opened", {"poll": poll}, correlation_id=poll["id"]
        )
        return poll

    @app.post("/v1/live-sessions/{session_id}/polls/{poll_id}/votes")
    async def cast_vote(
        session_id: str, poll_id: str, payload: VoteRequest, request: Request
    ) -> dict[str, Any]:
        poll = store_from(request).vote(poll_id, payload.user_id, payload.option_id)
        if poll["session_id"] != session_id:
            raise HTTPException(status_code=404, detail="poll does not belong to session")
        await broker_from(request).publish(
            session_id,
            "poll.updated",
            {"poll": poll},
            correlation_id=poll_id,
        )
        return poll

    @app.post("/v1/carts", status_code=201)
    async def create_cart(payload: CartCreate, request: Request) -> dict[str, Any]:
        return store_from(request).create_cart(payload.user_id)

    @app.get("/v1/carts/{cart_id}")
    async def get_cart(cart_id: str, request: Request) -> dict[str, Any]:
        return store_from(request).get_cart(cart_id)

    @app.post("/v1/carts/{cart_id}/items")
    async def add_cart_item(
        cart_id: str, payload: CartItemRequest, request: Request
    ) -> dict[str, Any]:
        return store_from(request).add_cart_item(cart_id, payload.sku, payload.quantity)

    @app.post("/v1/checkout-sessions", status_code=201)
    async def create_checkout(payload: CheckoutCreate, request: Request) -> dict[str, Any]:
        store = store_from(request)
        cart_before = store.get_cart(payload.cart_id)
        checkout = store.checkout(
            payload.cart_id, payload.session_id, payload.idempotency_key
        )
        if not checkout.get("idempotent_replay", False):
            await broker_from(request).publish(
                payload.session_id,
                "checkout.completed",
                {"checkout": checkout, "cart": cart_before},
                correlation_id=checkout["id"],
            )
            for item in cart_before["items"]:
                product = store.get_product(item["sku"])
                await broker_from(request).publish(
                    payload.session_id,
                    "inventory.updated",
                    {"product": product},
                    correlation_id=item["sku"],
                    causation_id=checkout["id"],
                )
        return checkout

    @app.post("/v1/live-sessions/{session_id}/segments:generate", status_code=202)
    async def generate_segment(
        session_id: str, payload: SegmentGenerateRequest, request: Request
    ) -> dict[str, Any]:
        generation: GenerationService = request.app.state.generation
        return await generation.generate(session_id, payload)

    @app.get("/v1/live-sessions/{session_id}/segments")
    async def list_segments(session_id: str, request: Request) -> list[dict[str, Any]]:
        return store_from(request).list_segments(session_id)

    @app.post("/v1/segments/{segment_id}:air")
    async def air_segment(
        segment_id: str, payload: SegmentAirRequest, request: Request
    ) -> dict[str, Any]:
        store = store_from(request)
        segment = store.get_segment(segment_id)
        program_time_ms = (
            payload.program_time_ms
            if payload.program_time_ms is not None
            else store.current_program_time_ms(segment["session_id"])
        )
        generation: GenerationService = request.app.state.generation
        return await generation.mark_on_air(segment_id, program_time_ms=program_time_ms)

    @app.post(resolved_settings.fal_webhook_path)
    async def fal_webhook(request: Request) -> dict[str, Any]:
        raw_body = await request.body()
        verifier: FalWebhookVerifier = request.app.state.verifier
        try:
            await verifier.verify(request.headers, raw_body)
        except WebhookVerificationError as exc:
            logger.warning("rejected fal webhook: %s", exc)
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        try:
            parsed = FalWebhookPayload.model_validate(json.loads(raw_body))
        except (json.JSONDecodeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="invalid fal webhook body") from exc
        generation: GenerationService = request.app.state.generation
        segment, processed = await generation.handle_webhook(parsed, raw_body)
        return {"accepted": True, "processed": processed, "segment": segment}

    @app.websocket("/v1/live-sessions/{session_id}/ws")
    async def room_socket(
        websocket: WebSocket,
        session_id: str,
        client_id: str = Query(default_factory=lambda: uuid.uuid4().hex),
        role: str = Query(default="viewer"),
        after_sequence: int = Query(default=0, ge=0),
    ) -> None:
        store: Store = websocket.app.state.store
        hub: RoomHub = websocket.app.state.hub
        broker: EventBroker = websocket.app.state.broker
        settings_: Settings = websocket.app.state.settings
        try:
            store.get_session(session_id)
        except NotFoundError:
            await websocket.close(code=4404, reason="session not found")
            return

        await hub.connect(session_id, websocket, client_id=client_id, role=role)
        try:
            snapshot = store.snapshot(
                session_id,
                after_sequence=after_sequence,
                replay_limit=settings_.event_replay_limit,
            )
            await hub.send_snapshot(
                session_id,
                websocket,
                {
                    "type": "session.snapshot",
                    "session_id": session_id,
                    "sequence": snapshot["last_sequence"],
                    "payload": snapshot,
                },
            )
            await hub.activate(session_id, websocket)
            while True:
                incoming = await websocket.receive_json()
                message_type = incoming.get("type")
                payload = incoming.get("payload") or {}
                if message_type == "presence.heartbeat":
                    await hub.send_personal(
                        session_id,
                        websocket,
                        {
                            "type": "presence.heartbeat_ack",
                            "session_id": session_id,
                            "payload": {"client_id": client_id},
                        },
                    )
                elif message_type == "chat.send":
                    content = str(payload.get("content", "")).strip()
                    if not content or len(content) > 280:
                        await hub.send_personal(
                            session_id,
                            websocket,
                            {"type": "error", "payload": {"detail": "invalid chat message"}},
                        )
                        continue
                    await broker.publish(
                        session_id,
                        "chat.message.published",
                        {
                            "message_id": f"msg_{uuid.uuid4().hex}",
                            "user_id": client_id,
                            "content": content,
                        },
                    )
                elif message_type == "vote.cast":
                    vote = VoteRequest.model_validate(
                        {
                            "user_id": client_id,
                            "option_id": payload.get("option_id"),
                        }
                    )
                    poll_id = str(payload.get("poll_id", ""))
                    poll = store.vote(poll_id, vote.user_id, vote.option_id)
                    if poll["session_id"] != session_id:
                        raise ValidationError("poll does not belong to session")
                    await broker.publish(
                        session_id,
                        "poll.updated",
                        {"poll": poll},
                        correlation_id=poll_id,
                    )
                elif message_type == "product.click":
                    sku = str(payload.get("sku", ""))
                    store.get_product(sku)
                    await broker.publish(
                        session_id,
                        "product.clicked",
                        {"sku": sku, "user_id": client_id},
                        correlation_id=sku,
                    )
                else:
                    await hub.send_personal(
                        session_id,
                        websocket,
                        {
                            "type": "error",
                            "payload": {"detail": f"unsupported message type: {message_type}"},
                        },
                    )
        except WebSocketDisconnect:
            pass
        except Exception as exc:
            logger.exception("websocket handler failed")
            try:
                await hub.send_personal(
                    session_id,
                    websocket,
                    {"type": "error", "payload": {"detail": str(exc)}},
                )
            except Exception:
                pass
        finally:
            await hub.disconnect(session_id, websocket)

    return app


app = create_app()
