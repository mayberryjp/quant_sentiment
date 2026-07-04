"""Sentiment intake service — orchestrates ``POST /sentiment`` logic.

Builds an immutable :class:`SentimentObservation` from a submission: canonicalizes
the subject, derives the label from the score, assigns a UUID and timestamps,
then persists it idempotently.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.models.domain import SentimentObservation
from app.models.requests import SentimentSubmission
from app.repository.postgres import SentimentRepository
from app.services.labels import derive_label
from app.services.subject_resolver import SubjectResolver


def ingest_observation(
    submission: SentimentSubmission, repo: SentimentRepository
) -> tuple[SentimentObservation, bool]:
    """Validate-derived, canonicalize, and persist an observation.

    Returns ``(record, is_duplicate)``.
    """
    now = datetime.now(timezone.utc)
    observation = SentimentObservation(
        sentiment_id=uuid4(),
        source=submission.source,
        idempotency_key=submission.idempotency_key,
        subject_type=submission.subject_type,
        subject=submission.subject,
        canonical_subject=SubjectResolver.resolve(
            submission.subject_type,
            submission.subject,
            submission.market,
            submission.locale,
        ),
        sentiment_label=derive_label(submission.sentiment_score),
        sentiment_score=submission.sentiment_score,
        confidence=submission.confidence,
        source_weight=submission.source_weight,
        horizon=submission.horizon,
        market=submission.market,
        locale=submission.locale,
        reason=submission.reason,
        tags=submission.tags,
        metadata=submission.metadata,
        observed_at=submission.observed_at or now,
        received_at=now,
    )
    return repo.insert_observation(observation)
