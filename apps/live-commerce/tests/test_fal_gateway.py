from livecommerce.fal_gateway import extract_media_url


def test_extract_media_url_supports_common_shapes() -> None:
    assert extract_media_url({"video": {"url": "https://cdn/video.mp4"}}) == "https://cdn/video.mp4"
    assert extract_media_url({"videos": [{"url": "https://cdn/video2.mp4"}]}) == "https://cdn/video2.mp4"
    assert extract_media_url({"images": [{"url": "https://cdn/image.png"}]}) == "https://cdn/image.png"
    assert extract_media_url({"video_url": "https://cdn/direct.mp4"}) == "https://cdn/direct.mp4"
    assert extract_media_url({"unrelated": True}) is None


import sys
from types import SimpleNamespace

import pytest

from livecommerce.config import Settings
from livecommerce.fal_gateway import FalQueueGateway


@pytest.mark.asyncio
async def test_queue_gateway_submits_with_configured_model_and_webhook(monkeypatch) -> None:
    captured = {}

    class FakeHandle:
        request_id = "fal-request-123"

    class FakeClient:
        def __init__(self, *, key):
            captured["key"] = key

        def submit(self, application, *, arguments, webhook_url):
            captured.update(
                application=application,
                arguments=arguments,
                webhook_url=webhook_url,
            )
            return FakeHandle()

    monkeypatch.setitem(sys.modules, "fal_client", SimpleNamespace(SyncClient=FakeClient))
    settings = Settings(
        app_env="test",
        fal_mode="queue",
        fal_key="secret-key",
        fal_model_id="fal-ai/approved-video-model",
        public_base_url="https://live.example",
    )
    gateway = FalQueueGateway(settings)
    result = await gateway.submit(
        model_id="fal-ai/approved-video-model",
        arguments={"prompt": "demo"},
        webhook_url="https://live.example/v1/webhooks/fal",
    )

    assert result.request_id == "fal-request-123"
    assert result.provider == "fal"
    assert captured == {
        "key": "secret-key",
        "application": "fal-ai/approved-video-model",
        "arguments": {"prompt": "demo"},
        "webhook_url": "https://live.example/v1/webhooks/fal",
    }
