"""Domain models for the sentiment aggregator.

All models use Pydantic v2 and mirror the columns of
``sentiment.sentiment_observations``. Timestamps are always normalized to the
container's local timezone (e.g. America/New_York) so behaviour is identical
across PostgreSQL (TIMESTAMPTZ) and the SQLite test backend (which stores naive
datetimes).
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.timeutil import local_tz


class SubjectType(str, enum.Enum):
    ticker = "ticker"
    sector = "sector"
    theme = "theme"
    market = "market"


class SentimentLabel(str, enum.Enum):
    bullish = "bullish"
    bearish = "bearish"
    neutral = "neutral"


class SentimentObservation(BaseModel):
    """A stored, immutable sentiment observation."""

    sentiment_id: UUID
    source: str
    idempotency_key: str
    subject_type: SubjectType = SubjectType.ticker
    subject: str
    canonical_subject: str
    sentiment_label: SentimentLabel
    sentiment_score: float
    confidence: float | None = None
    source_weight: float | None = None
    horizon: str | None = None
    market: str = "stocks"
    locale: str = "us"
    reason: str = ""
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    observed_at: datetime
    received_at: datetime
    schema_version: int = 1

    @field_validator("observed_at", "received_at", mode="after")
    @classmethod
    def _ensure_local(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=local_tz())
        return value.astimezone(local_tz())
