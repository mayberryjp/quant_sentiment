"""Request schemas for the sentiment API."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.config import settings
from app.models.domain import SubjectType


class SentimentSubmission(BaseModel):
    """Body of ``POST /sentiment``.

    Note: ``sentiment_label`` is intentionally absent — it is derived from
    ``sentiment_score`` by the service.
    """

    source: str = Field(..., min_length=1, max_length=settings.max_source_length)
    idempotency_key: str = Field(
        ..., min_length=1, max_length=settings.max_idempotency_key_length
    )
    subject_type: SubjectType = SubjectType.ticker
    subject: str = Field(..., min_length=1, max_length=settings.max_subject_length)
    sentiment_score: float = Field(..., ge=settings.score_min, le=settings.score_max)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    source_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    horizon: str | None = Field(default=None, max_length=32)
    market: str = Field(default="stocks", max_length=32)
    locale: str = Field(default="us", max_length=8)
    reason: str = Field(default="", max_length=settings.max_reason_length)
    observed_at: datetime | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("tags")
    @classmethod
    def _limit_tags(cls, value: list[str]) -> list[str]:
        if len(value) > settings.max_tags:
            raise ValueError(f"too many tags (max {settings.max_tags})")
        return value

    @field_validator("metadata")
    @classmethod
    def _limit_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        size = len(json.dumps(value).encode("utf-8"))
        if size > settings.max_metadata_bytes:
            raise ValueError(f"metadata too large (max {settings.max_metadata_bytes} bytes)")
        return value
