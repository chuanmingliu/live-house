from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SessionState(StrEnum):
    DRAFT = "DRAFT"
    SCHEDULED = "SCHEDULED"
    WARMING = "WARMING"
    READY = "READY"
    LIVE = "LIVE"
    DEGRADED = "DEGRADED"
    ENDING = "ENDING"
    ENDED = "ENDED"


class PollState(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class SegmentState(StrEnum):
    PLANNED = "PLANNED"
    MODERATED = "MODERATED"
    SUBMITTED = "SUBMITTED"
    GENERATING = "GENERATING"
    QA = "QA"
    READY = "READY"
    ON_AIR = "ON_AIR"
    FAILED = "FAILED"
    STALE = "STALE"
    CANCELLED = "CANCELLED"


class SessionCreate(ApiModel):
    title: str = Field(min_length=1, max_length=120)
    playback_url: str | None = Field(default="/static/demo-program.mp4", max_length=2048)


class ProductCreate(ApiModel):
    sku: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=1000)
    price_minor: int = Field(ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    inventory: int = Field(default=0, ge=0)
    image_url: str | None = Field(default=None, max_length=2048)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class ProductPinRequest(ApiModel):
    program_time_ms: int | None = Field(default=None, ge=0)


class PollOption(ApiModel):
    id: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=120)


class PollCreate(ApiModel):
    question: str = Field(min_length=1, max_length=240)
    options: list[PollOption] = Field(min_length=2, max_length=6)

    @field_validator("options")
    @classmethod
    def unique_option_ids(cls, options: list[PollOption]) -> list[PollOption]:
        ids = [option.id for option in options]
        if len(ids) != len(set(ids)):
            raise ValueError("poll option ids must be unique")
        return options


class VoteRequest(ApiModel):
    user_id: str = Field(min_length=1, max_length=128)
    option_id: str = Field(min_length=1, max_length=64)


class CartCreate(ApiModel):
    user_id: str = Field(min_length=1, max_length=128)


class CartItemRequest(ApiModel):
    sku: str = Field(min_length=1, max_length=64)
    quantity: int = Field(default=1, ge=1, le=99)


class CheckoutCreate(ApiModel):
    cart_id: str = Field(min_length=1, max_length=128)
    session_id: str = Field(min_length=1, max_length=128)
    idempotency_key: str = Field(min_length=8, max_length=128)


class SegmentGenerateRequest(ApiModel):
    prompt: str = Field(min_length=1, max_length=4000)
    product_skus: list[str] = Field(default_factory=list, max_length=20)
    duration_ms: int = Field(default=5000, ge=1000, le=30000)
    arguments: dict[str, Any] | None = None


class SegmentAirRequest(ApiModel):
    program_time_ms: int | None = Field(default=None, ge=0)


class EventEnvelope(BaseModel):
    event_id: str
    type: str
    occurred_at: datetime
    session_id: str
    sequence: int
    program_time_ms: int | None = None
    correlation_id: str | None = None
    causation_id: str | None = None
    payload: dict[str, Any]


class FalWebhookPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    request_id: str
    gateway_request_id: str | None = None
    status: str
    payload: dict[str, Any] | None = None
    error: str | None = None
    payload_error: str | None = None
