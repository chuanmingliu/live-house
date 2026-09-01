from __future__ import annotations

import base64
import hashlib
import json
import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from livecommerce.webhook_verifier import FalWebhookVerifier, WebhookVerificationError


def _signature_fixture() -> tuple[bytes, dict[str, str], list[dict[str, str]]]:
    private_key = Ed25519PrivateKey.generate()
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    encoded = base64.urlsafe_b64encode(public_bytes).decode("ascii").rstrip("=")
    body = json.dumps(
        {"request_id": "req-1", "status": "OK", "payload": {"video": {"url": "x"}}},
        separators=(",", ":"),
    ).encode("utf-8")
    timestamp = str(int(time.time()))
    message = "\n".join(
        ["req-1", "user-1", timestamp, hashlib.sha256(body).hexdigest()]
    ).encode("utf-8")
    signature = private_key.sign(message).hex()
    headers = {
        "x-fal-webhook-request-id": "req-1",
        "x-fal-webhook-user-id": "user-1",
        "x-fal-webhook-timestamp": timestamp,
        "x-fal-webhook-signature": signature,
    }
    return body, headers, [{"x": encoded}]


@pytest.mark.asyncio
async def test_valid_signature_is_accepted() -> None:
    body, headers, keys = _signature_fixture()

    async def fetcher() -> list[dict[str, str]]:
        return keys

    verifier = FalWebhookVerifier(jwks_url="unused", fetcher=fetcher)
    await verifier.verify(headers, body)


@pytest.mark.asyncio
async def test_modified_body_is_rejected() -> None:
    body, headers, keys = _signature_fixture()

    async def fetcher() -> list[dict[str, str]]:
        return keys

    verifier = FalWebhookVerifier(jwks_url="unused", fetcher=fetcher)
    with pytest.raises(WebhookVerificationError):
        await verifier.verify(headers, body + b" ")


@pytest.mark.asyncio
async def test_old_timestamp_is_rejected() -> None:
    body, headers, keys = _signature_fixture()
    headers["x-fal-webhook-timestamp"] = str(int(time.time()) - 301)

    async def fetcher() -> list[dict[str, str]]:
        return keys

    verifier = FalWebhookVerifier(jwks_url="unused", fetcher=fetcher)
    with pytest.raises(WebhookVerificationError, match="timestamp"):
        await verifier.verify(headers, body)
