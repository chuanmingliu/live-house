from __future__ import annotations

import asyncio
import base64
import hashlib
import time
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


class WebhookVerificationError(ValueError):
    pass


JwksFetcher = Callable[[], Awaitable[list[dict[str, Any]]]]


class FalWebhookVerifier:
    """Verify fal's ED25519 webhook signature over the raw request body."""

    def __init__(
        self,
        *,
        jwks_url: str,
        enabled: bool = True,
        max_clock_skew_seconds: int = 300,
        cache_seconds: int = 24 * 60 * 60,
        fetcher: JwksFetcher | None = None,
    ) -> None:
        self.jwks_url = jwks_url
        self.enabled = enabled
        self.max_clock_skew_seconds = max_clock_skew_seconds
        self.cache_seconds = cache_seconds
        self.fetcher = fetcher
        self._cache: list[dict[str, Any]] | None = None
        self._cache_at = 0.0
        self._lock = asyncio.Lock()

    async def verify(self, headers: Mapping[str, str], body: bytes) -> None:
        if not self.enabled:
            return

        request_id = headers.get("x-fal-webhook-request-id")
        user_id = headers.get("x-fal-webhook-user-id")
        timestamp = headers.get("x-fal-webhook-timestamp")
        signature_hex = headers.get("x-fal-webhook-signature")
        if not all((request_id, user_id, timestamp, signature_hex)):
            raise WebhookVerificationError("missing required fal webhook signature headers")

        try:
            timestamp_int = int(timestamp)
        except (TypeError, ValueError) as exc:
            raise WebhookVerificationError("invalid fal webhook timestamp") from exc
        if abs(int(time.time()) - timestamp_int) > self.max_clock_skew_seconds:
            raise WebhookVerificationError("fal webhook timestamp is outside the allowed window")

        try:
            signature = bytes.fromhex(signature_hex)
        except ValueError as exc:
            raise WebhookVerificationError("invalid fal webhook signature encoding") from exc

        message = "\n".join(
            [request_id, user_id, timestamp, hashlib.sha256(body).hexdigest()]
        ).encode("utf-8")
        keys = await self._get_keys()
        for item in keys:
            encoded = item.get("x")
            if not isinstance(encoded, str):
                continue
            try:
                padding = "=" * (-len(encoded) % 4)
                public_bytes = base64.urlsafe_b64decode(encoded + padding)
                Ed25519PublicKey.from_public_bytes(public_bytes).verify(signature, message)
                return
            except (ValueError, InvalidSignature):
                continue
        raise WebhookVerificationError("fal webhook signature verification failed")

    async def _get_keys(self) -> list[dict[str, Any]]:
        now = time.monotonic()
        if self._cache is not None and now - self._cache_at < self.cache_seconds:
            return self._cache
        async with self._lock:
            now = time.monotonic()
            if self._cache is not None and now - self._cache_at < self.cache_seconds:
                return self._cache
            if self.fetcher is not None:
                keys = await self.fetcher()
            else:
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.get(self.jwks_url)
                    response.raise_for_status()
                    keys = response.json().get("keys", [])
            if not isinstance(keys, list) or not keys:
                raise WebhookVerificationError("fal JWKS did not contain any keys")
            self._cache = keys
            self._cache_at = time.monotonic()
            return keys
