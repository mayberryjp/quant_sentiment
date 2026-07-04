"""Response schemas for the sentiment API."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class SentimentAcceptedResponse(BaseModel):
    """Returned by ``POST /sentiment``."""

    status: str  # "accepted" | "duplicate"
    sentiment_id: UUID
    sentiment_label: str
    subject_type: str
    canonical_subject: str


class SentimentDetailResponse(BaseModel):
    """Full detail of a stored observation."""

    sentiment_id: UUID
    source: str
    idempotency_key: str
    subject_type: str
    subject: str
    canonical_subject: str
    sentiment_label: str
    sentiment_score: float
    confidence: float | None = None
    source_weight: float | None = None
    horizon: str | None = None
    market: str
    locale: str
    reason: str
    tags: list[str]
    metadata: dict[str, Any]
    observed_at: datetime
    received_at: datetime
    schema_version: int


class SentimentListResponse(BaseModel):
    """A page of observations returned by ``GET /sentiment/recent``."""

    items: list[SentimentDetailResponse]
    total: int
    page: int
    page_size: int
