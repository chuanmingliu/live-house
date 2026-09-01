from __future__ import annotations

import pytest
from pydantic import ValidationError

from livecommerce.model_adapters import H3_MAX_TEXT_TO_VIDEO, build_model_arguments
from livecommerce.models import SegmentGenerateRequest


def test_h3_max_adapter_builds_safe_default_payload() -> None:
    payload = build_model_arguments(
        H3_MAX_TEXT_TO_VIDEO,
        SegmentGenerateRequest(prompt="A product beauty shot", duration_ms=5000),
    )
    assert payload == {
        "prompt": "A product beauty shot",
        "duration": 5,
        "resolution": "768P",
        "enable_safety_checker": True,
        "prompt_expansion_mode": "balanced",
        "aspect_ratio": "16:9",
        "sync_mode": False,
    }


def test_h3_max_adapter_rejects_unknown_arguments() -> None:
    request = SegmentGenerateRequest(
        prompt="A product beauty shot",
        duration_ms=5000,
        arguments={"unknown_provider_field": True},
    )
    with pytest.raises(ValidationError):
        build_model_arguments(H3_MAX_TEXT_TO_VIDEO, request)


def test_generic_adapter_preserves_explicit_arguments() -> None:
    request = SegmentGenerateRequest(
        prompt="A product beauty shot",
        arguments={"prompt": "provider prompt", "custom": 1},
    )
    assert build_model_arguments("vendor/custom", request) == {
        "prompt": "provider prompt",
        "custom": 1,
    }


def test_h3_max_adapter_rejects_unsupported_duration() -> None:
    request = SegmentGenerateRequest(prompt="Long scene", duration_ms=30000)
    with pytest.raises(ValidationError):
        build_model_arguments(H3_MAX_TEXT_TO_VIDEO, request)
