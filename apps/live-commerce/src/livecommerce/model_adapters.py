from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .models import SegmentGenerateRequest


H3_MAX_TEXT_TO_VIDEO = "minimax/h3-max/text-to-video"


class H3MaxTextToVideoArguments(BaseModel):
    """Typed subset of the public H3 Max text-to-video input schema."""

    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1, max_length=4000)
    duration: int = Field(default=5, ge=5, le=15)
    resolution: Literal["480P", "768P"] = "768P"
    enable_safety_checker: bool = True
    prompt_expansion_mode: Literal["balanced", "quality"] = "balanced"
    aspect_ratio: Literal["21:9", "16:9", "4:3", "1:1", "3:4", "9:16"] = "16:9"
    sync_mode: bool = False


def build_model_arguments(
    model_id: str | None, request: SegmentGenerateRequest
) -> dict[str, Any]:
    """Compile a scene request into a provider-specific payload.

    Known models get strict validation. Unknown models retain the generic `prompt`
    contract until a typed adapter is added.
    """

    if model_id == H3_MAX_TEXT_TO_VIDEO:
        seconds = max(5, round(request.duration_ms / 1000))
        base: dict[str, Any] = {
            "prompt": request.prompt,
            "duration": seconds,
            "resolution": "768P",
            "enable_safety_checker": True,
            "prompt_expansion_mode": "balanced",
            "aspect_ratio": "16:9",
            "sync_mode": False,
        }
        if request.arguments:
            base.update(request.arguments)
        return H3MaxTextToVideoArguments.model_validate(base).model_dump()

    if request.arguments is not None:
        return request.arguments
    return {"prompt": request.prompt}
