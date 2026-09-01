from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from .config import Settings


@dataclass(slots=True)
class GenerationSubmission:
    request_id: str
    provider: str


class GenerationGateway(Protocol):
    async def submit(
        self,
        *,
        model_id: str | None,
        arguments: dict[str, Any],
        webhook_url: str,
    ) -> GenerationSubmission: ...


class MockGenerationGateway:
    async def submit(
        self,
        *,
        model_id: str | None,
        arguments: dict[str, Any],
        webhook_url: str,
    ) -> GenerationSubmission:
        del model_id, arguments, webhook_url
        return GenerationSubmission(request_id=f"mock_{uuid.uuid4().hex}", provider="mock")


class FalQueueGateway:
    """Thin adapter over fal_client.submit.

    Importing fal_client is delayed so mock mode works without the optional dependency.
    """

    def __init__(self, settings: Settings):
        settings.validate_fal_configuration()
        self.settings = settings

    async def submit(
        self,
        *,
        model_id: str | None,
        arguments: dict[str, Any],
        webhook_url: str,
    ) -> GenerationSubmission:
        resolved_model = model_id or self.settings.fal_model_id
        if resolved_model != self.settings.fal_model_id:
            raise ValueError("requested model is not in the configured allowlist")

        def _submit() -> str:
            try:
                import fal_client
            except ImportError as exc:
                raise RuntimeError(
                    "fal-client is not installed; run `pip install -e .[fal]`"
                ) from exc
            client = fal_client.SyncClient(key=self.settings.fal_key)
            handle = client.submit(
                resolved_model,
                arguments=arguments,
                webhook_url=webhook_url,
            )
            return handle.request_id

        request_id = await asyncio.to_thread(_submit)
        return GenerationSubmission(request_id=request_id, provider="fal")


def build_generation_gateway(settings: Settings) -> GenerationGateway:
    if settings.fal_mode == "queue":
        return FalQueueGateway(settings)
    return MockGenerationGateway()


def extract_media_url(payload: dict[str, Any] | None) -> str | None:
    """Extract common fal media response shapes without coupling to one model."""
    if not payload:
        return None

    direct_candidates = [payload.get("url"), payload.get("video_url"), payload.get("audio_url")]
    for candidate in direct_candidates:
        if isinstance(candidate, str):
            return candidate

    for singular in ("video", "image", "audio", "file"):
        value = payload.get(singular)
        if isinstance(value, dict) and isinstance(value.get("url"), str):
            return value["url"]

    for plural in ("videos", "images", "audios", "files"):
        value = payload.get(plural)
        if isinstance(value, list) and value:
            first = value[0]
            if isinstance(first, dict) and isinstance(first.get("url"), str):
                return first["url"]
            if isinstance(first, str):
                return first
    return None
