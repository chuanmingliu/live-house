from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Coroutine
from datetime import UTC, datetime
from typing import Any

from .config import Settings
from .events import EventBroker
from .fal_gateway import GenerationGateway, extract_media_url
from .model_adapters import build_model_arguments
from .models import FalWebhookPayload, SegmentGenerateRequest, SegmentState
from .store import ConflictError, Store


TERMINAL_SEGMENT_STATES = {
    SegmentState.READY.value,
    SegmentState.ON_AIR.value,
    SegmentState.FAILED.value,
    SegmentState.STALE.value,
    SegmentState.CANCELLED.value,
}


class GenerationService:
    def __init__(
        self,
        *,
        store: Store,
        broker: EventBroker,
        gateway: GenerationGateway,
        settings: Settings,
    ) -> None:
        self.store = store
        self.broker = broker
        self.gateway = gateway
        self.settings = settings
        self._tasks: set[asyncio.Task[None]] = set()

    async def close(self) -> None:
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()

    def _spawn(self, coroutine: Coroutine[Any, Any, None]) -> None:
        task = asyncio.create_task(coroutine)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def generate(
        self, session_id: str, request: SegmentGenerateRequest
    ) -> dict[str, Any]:
        segment = self.store.create_segment(
            session_id,
            request,
            model_id=self.settings.fal_model_id,
            deadline_seconds=self.settings.fal_job_deadline_seconds,
        )
        await self.broker.publish(
            session_id,
            "scene.plan.created",
            {"segment": segment},
            correlation_id=segment["id"],
        )

        # The MVP's moderation gate is deterministic and deliberately conservative.
        if self._looks_unsafe(request.prompt):
            segment = self.store.update_segment(
                segment["id"],
                state=SegmentState.FAILED,
                error="prompt rejected by starter policy",
            )
            await self.broker.publish(
                session_id,
                "segment.fallback_activated",
                {"segment": segment, "reason": "prompt_policy"},
                correlation_id=segment["id"],
            )
            return segment

        segment = self.store.update_segment(segment["id"], state=SegmentState.MODERATED)
        await self.broker.publish(
            session_id,
            "scene.plan.approved",
            {"segment_id": segment["id"]},
            correlation_id=segment["id"],
        )

        arguments = build_model_arguments(self.settings.fal_model_id, request)
        submission = await self.gateway.submit(
            model_id=self.settings.fal_model_id,
            arguments=arguments,
            webhook_url=self.settings.webhook_url,
        )
        segment = self.store.update_segment(
            segment["id"],
            state=SegmentState.SUBMITTED,
            fal_request_id=submission.request_id,
        )
        await self.broker.publish(
            session_id,
            "fal.job.submitted",
            {
                "segment_id": segment["id"],
                "request_id": submission.request_id,
                "provider": submission.provider,
            },
            correlation_id=segment["id"],
            causation_id=submission.request_id,
        )

        self._spawn(self._deadline_watch(segment["id"]))
        if submission.provider == "mock":
            self._spawn(self._complete_mock(segment["id"]))
        return segment

    async def _deadline_watch(self, segment_id: str) -> None:
        segment = self.store.get_segment(segment_id)
        deadline = datetime.fromisoformat(segment["deadline_at"])
        delay = max(0.0, (deadline - datetime.now(UTC)).total_seconds())
        await asyncio.sleep(delay)
        segment = self.store.get_segment(segment_id)
        if segment["state"] in TERMINAL_SEGMENT_STATES:
            return
        segment = self.store.update_segment(segment_id, state=SegmentState.STALE)
        await self.broker.publish(
            segment["session_id"],
            "segment.fallback_activated",
            {"segment_id": segment_id, "reason": "deadline_missed"},
            correlation_id=segment_id,
            causation_id=segment.get("fal_request_id"),
        )

    async def _complete_mock(self, segment_id: str) -> None:
        await asyncio.sleep(self.settings.mock_generation_delay_seconds)
        segment = self.store.get_segment(segment_id)
        if segment["state"] == SegmentState.STALE.value:
            return
        segment = self.store.update_segment(
            segment_id,
            state=SegmentState.QA,
            asset_url=self.settings.mock_asset_url,
        )
        await self.broker.publish(
            segment["session_id"],
            "fal.job.completed",
            {
                "segment_id": segment_id,
                "request_id": segment["fal_request_id"],
                "asset_url": segment["asset_url"],
            },
            correlation_id=segment_id,
            causation_id=segment["fal_request_id"],
        )
        await self._mark_ready_or_stale(segment_id)

    async def handle_webhook(
        self, webhook: FalWebhookPayload, raw_body: bytes
    ) -> tuple[dict[str, Any], bool]:
        body_hash = hashlib.sha256(raw_body).hexdigest()
        segment = self.store.find_segment_by_request_id(webhook.request_id)
        claimed = self.store.claim_webhook(webhook.request_id, body_hash)
        if not claimed:
            return segment, False

        try:
            processed = await self._process_webhook(segment, webhook)
        except Exception:
            self.store.release_webhook(webhook.request_id)
            raise
        else:
            self.store.complete_webhook(webhook.request_id)
            return processed, True

    async def _process_webhook(
        self, segment: dict[str, Any], webhook: FalWebhookPayload
    ) -> dict[str, Any]:
        if webhook.status.upper() != "OK":
            segment = self.store.update_segment(
                segment["id"],
                state=SegmentState.FAILED,
                error=webhook.error or webhook.payload_error or "fal request failed",
            )
            await self.broker.publish(
                segment["session_id"],
                "fal.job.failed",
                {"segment": segment},
                correlation_id=segment["id"],
                causation_id=webhook.request_id,
            )
            await self.broker.publish(
                segment["session_id"],
                "segment.fallback_activated",
                {"segment_id": segment["id"], "reason": "fal_failure"},
                correlation_id=segment["id"],
            )
            return segment

        asset_url = extract_media_url(webhook.payload)
        if asset_url is None:
            segment = self.store.update_segment(
                segment["id"],
                state=SegmentState.FAILED,
                error="fal webhook did not contain a supported media URL",
            )
            await self.broker.publish(
                segment["session_id"],
                "segment.fallback_activated",
                {"segment_id": segment["id"], "reason": "unsupported_payload"},
                correlation_id=segment["id"],
            )
            return segment

        # A late result is retained for audit/inspection but can never transition back
        # to READY after the deadline fallback has fired.
        if segment["state"] == SegmentState.STALE.value:
            segment = self.store.update_segment(segment["id"], asset_url=asset_url)
            await self.broker.publish(
                segment["session_id"],
                "fal.job.completed",
                {
                    "segment_id": segment["id"],
                    "request_id": webhook.request_id,
                    "asset_url": asset_url,
                    "late": True,
                },
                correlation_id=segment["id"],
                causation_id=webhook.request_id,
            )
            return segment

        segment = self.store.update_segment(
            segment["id"], state=SegmentState.QA, asset_url=asset_url
        )
        await self.broker.publish(
            segment["session_id"],
            "fal.job.completed",
            {
                "segment_id": segment["id"],
                "request_id": webhook.request_id,
                "asset_url": asset_url,
            },
            correlation_id=segment["id"],
            causation_id=webhook.request_id,
        )
        return await self._mark_ready_or_stale(segment["id"])

    async def _mark_ready_or_stale(self, segment_id: str) -> dict[str, Any]:
        segment = self.store.get_segment(segment_id)
        deadline = datetime.fromisoformat(segment["deadline_at"])
        if datetime.now(UTC) > deadline:
            segment = self.store.update_segment(segment_id, state=SegmentState.STALE)
            await self.broker.publish(
                segment["session_id"],
                "segment.fallback_activated",
                {"segment_id": segment_id, "reason": "deadline_missed"},
                correlation_id=segment_id,
            )
            return segment

        # This is the first QA seam. Production replaces it with decode, safety,
        # product-fidelity, loudness, duration, and human-review checks.
        await self.broker.publish(
            segment["session_id"],
            "segment.qa.passed",
            {"segment_id": segment_id, "checks": ["media_url_present"]},
            correlation_id=segment_id,
        )
        segment = self.store.update_segment(segment_id, state=SegmentState.READY)
        await self.broker.publish(
            segment["session_id"],
            "segment.ready",
            {"segment": segment},
            correlation_id=segment_id,
        )
        return segment

    async def mark_on_air(
        self, segment_id: str, *, program_time_ms: int
    ) -> dict[str, Any]:
        segment = self.store.get_segment(segment_id)
        if segment["state"] != SegmentState.READY.value:
            raise ConflictError("only READY segments can go on air")
        segment = self.store.update_segment(
            segment_id,
            state=SegmentState.ON_AIR,
            on_air_program_time_ms=program_time_ms,
        )
        await self.broker.publish(
            segment["session_id"],
            "segment.on_air",
            {"segment": segment},
            program_time_ms=program_time_ms,
            correlation_id=segment_id,
        )
        return segment

    @staticmethod
    def _looks_unsafe(prompt: str) -> bool:
        normalized = prompt.casefold()
        blocked_fragments = {
            "guaranteed cure",
            "guaranteed profit",
            "fake discount",
            "ignore moderation",
            "bypass policy",
        }
        return any(fragment in normalized for fragment in blocked_fragments)
