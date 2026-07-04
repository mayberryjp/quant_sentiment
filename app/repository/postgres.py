"""Append-only repository for sentiment observations.

The repository exposes only insert and read operations. There is deliberately
**no** update or delete path: sentiment is immutable once stored. Deduplication
is enforced by the ``(source, idempotency_key)`` unique constraint; a repeated
submission returns the already-stored record.

All statements use SQLAlchemy Core expression language (parameterized), so the
same code runs against PostgreSQL (production) and SQLite (tests).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import Engine
from sqlalchemy.exc import IntegrityError

from app.models.domain import SentimentObservation
from app.repository.schema import sentiment_observations as T
# Domain fields that map 1:1 onto table columns (excludes the surrogate PK).
_COLUMNS = [
    "sentiment_id",
    "source",
    "idempotency_key",
    "subject_type",
    "subject",
    "canonical_subject",
    "sentiment_label",
    "sentiment_score",
    "confidence",
    "source_weight",
    "horizon",
    "market",
    "locale",
    "reason",
    "tags",
    "metadata",
    "observed_at",
    "received_at",
    "schema_version",
]


def _to_row(obs: SentimentObservation) -> dict:
    data = obs.model_dump()
    data["subject_type"] = obs.subject_type.value
    data["sentiment_label"] = obs.sentiment_label.value
    return {col: data[col] for col in _COLUMNS}


def _from_row(row) -> SentimentObservation:
    data = dict(row)
    data.pop("id", None)
    return SentimentObservation(**data)


def _as_uuid(value: UUID | str) -> UUID | None:
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


class SentimentRepository:
    """Encapsulates every database interaction for the sentiment domain."""

    def __init__(self, engine: Engine):
        self.engine = engine

    def insert_observation(
        self, obs: SentimentObservation
    ) -> tuple[SentimentObservation, bool]:
        """Persist an observation.

        Returns ``(record, is_duplicate)``. If an observation with the same
        ``(source, idempotency_key)`` already exists, the stored record is
        returned unchanged and ``is_duplicate`` is ``True``.
        """
        existing = self.get_by_source_and_key(obs.source, obs.idempotency_key)
        if existing is not None:
            return existing, True
        try:
            with self.engine.begin() as conn:
                conn.execute(sa.insert(T).values(**_to_row(obs)))
        except IntegrityError:
            # Lost a race on the unique constraint: fetch the winner.
            existing = self.get_by_source_and_key(obs.source, obs.idempotency_key)
            if existing is not None:
                return existing, True
            raise
        return obs, False

    def get_by_id(self, sentiment_id: UUID | str) -> SentimentObservation | None:
        sid = _as_uuid(sentiment_id)
        if sid is None:
            return None
        with self.engine.connect() as conn:
            row = (
                conn.execute(sa.select(T).where(T.c.sentiment_id == sid))
                .mappings()
                .first()
            )
        return _from_row(row) if row is not None else None

    def get_by_source_and_key(
        self, source: str, idempotency_key: str
    ) -> SentimentObservation | None:
        with self.engine.connect() as conn:
            row = (
                conn.execute(
                    sa.select(T).where(
                        T.c.source == source,
                        T.c.idempotency_key == idempotency_key,
                    )
                )
                .mappings()
                .first()
            )
        return _from_row(row) if row is not None else None

    def list_observations(
        self,
        *,
        source: str | None = None,
        subject: str | None = None,
        subject_type: str | None = None,
        sentiment_label: str | None = None,
        market: str | None = None,
        locale: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[SentimentObservation], int]:
        """Return a page of observations (newest received first) and the total.

        Time filters (``since``/``until``) apply to ``received_at``. Subject
        matching is case-insensitive against the canonical subject.
        """
        conditions: list = []
        if source:
            conditions.append(T.c.source == source)
        if subject:
            conditions.append(
                sa.func.lower(T.c.canonical_subject) == subject.strip().lower()
            )
        if subject_type:
            conditions.append(T.c.subject_type == subject_type)
        if sentiment_label:
            conditions.append(T.c.sentiment_label == sentiment_label)
        if market:
            conditions.append(T.c.market == market)
        if locale:
            conditions.append(T.c.locale == locale)
        if since is not None:
            conditions.append(T.c.received_at >= since)
        if until is not None:
            conditions.append(T.c.received_at <= until)

        where = sa.and_(*conditions) if conditions else sa.true()
        offset = max(page - 1, 0) * page_size

        with self.engine.connect() as conn:
            total = conn.execute(
                sa.select(sa.func.count()).select_from(T).where(where)
            ).scalar_one()
            rows = (
                conn.execute(
                    sa.select(T)
                    .where(where)
                    .order_by(T.c.received_at.desc(), T.c.id.desc())
                    .limit(page_size)
                    .offset(offset)
                )
                .mappings()
                .all()
            )
        return [_from_row(r) for r in rows], int(total)

    def get_by_subject(
        self,
        subject: str,
        subject_type: str | None = None,
        limit: int = 100,
    ) -> list[SentimentObservation]:
        """Return observations for a subject, newest observed first."""
        conditions = [sa.func.lower(T.c.canonical_subject) == subject.strip().lower()]
        if subject_type:
            conditions.append(T.c.subject_type == subject_type)
        with self.engine.connect() as conn:
            rows = (
                conn.execute(
                    sa.select(T)
                    .where(sa.and_(*conditions))
                    .order_by(T.c.observed_at.desc(), T.c.id.desc())
                    .limit(limit)
                )
                .mappings()
                .all()
            )
        return [_from_row(r) for r in rows]

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------

    @staticmethod
    def _aggregation_conditions(
        canonical_subject: str,
        subject_type: str | None,
        source: str | None,
        min_confidence: float | None,
        time_col,
        since: datetime,
    ) -> list:
        conditions = [
            sa.func.lower(T.c.canonical_subject) == canonical_subject.lower(),
            time_col >= since,
        ]
        if subject_type:
            conditions.append(T.c.subject_type == subject_type)
        if source:
            conditions.append(T.c.source == source)
        if min_confidence is not None:
            conditions.append(T.c.confidence >= min_confidence)
        return conditions

    def aggregate(
        self,
        *,
        canonical_subject: str,
        subject_type: str | None = None,
        source: str | None = None,
        min_confidence: float | None = None,
        time_basis: str = "observed_at",
        since: datetime,
    ) -> dict:
        """Compute aggregates for a subject over ``[since, now]``.

        ``confidence_weighted`` uses weight = coalesce(confidence, 1) *
        coalesce(source_weight, 1).
        """
        time_col = T.c.observed_at if time_basis == "observed_at" else T.c.received_at
        weight = sa.func.coalesce(T.c.confidence, 1.0) * sa.func.coalesce(
            T.c.source_weight, 1.0
        )
        where = sa.and_(
            *self._aggregation_conditions(
                canonical_subject, subject_type, source, min_confidence, time_col, since
            )
        )
        with self.engine.connect() as conn:
            row = conn.execute(
                sa.select(
                    sa.func.count().label("count"),
                    sa.func.avg(T.c.sentiment_score).label("mean_score"),
                    sa.func.sum(T.c.sentiment_score * weight).label("weighted_sum"),
                    sa.func.sum(weight).label("weight_sum"),
                    sa.func.max(time_col).label("latest"),
                ).where(where)
            ).mappings().first()
            label_rows = conn.execute(
                sa.select(T.c.sentiment_label, sa.func.count().label("n"))
                .where(where)
                .group_by(T.c.sentiment_label)
            ).all()
            sources = list(
                conn.execute(
                    sa.select(T.c.source).where(where).distinct()
                ).scalars().all()
            )
        return {
            "count": int(row["count"] or 0),
            "mean_score": float(row["mean_score"]) if row["mean_score"] is not None else None,
            "weighted_sum": float(row["weighted_sum"]) if row["weighted_sum"] is not None else None,
            "weight_sum": float(row["weight_sum"]) if row["weight_sum"] is not None else None,
            "latest": row["latest"],
            "label_counts": {label: int(n) for label, n in label_rows},
            "sources": sorted(sources),
        }

    def fetch_window_rows(
        self,
        *,
        canonical_subject: str,
        subject_type: str | None = None,
        source: str | None = None,
        min_confidence: float | None = None,
        time_basis: str = "observed_at",
        since: datetime,
    ) -> list[dict]:
        """Return lightweight rows in the window for Python-side bucketing."""
        time_col = T.c.observed_at if time_basis == "observed_at" else T.c.received_at
        where = sa.and_(
            *self._aggregation_conditions(
                canonical_subject, subject_type, source, min_confidence, time_col, since
            )
        )
        with self.engine.connect() as conn:
            rows = (
                conn.execute(
                    sa.select(
                        time_col.label("t"),
                        T.c.sentiment_score.label("score"),
                        T.c.confidence.label("confidence"),
                        T.c.source_weight.label("source_weight"),
                        T.c.sentiment_label.label("label"),
                    )
                    .where(where)
                    .order_by(time_col.asc())
                )
                .mappings()
                .all()
            )
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Operational
    # ------------------------------------------------------------------

    def ping(self) -> bool:
        """Return True if the database answers a trivial query."""
        try:
            with self.engine.connect() as conn:
                conn.execute(sa.text("SELECT 1"))
            return True
        except Exception:  # noqa: BLE001 - readiness must not raise
            return False

    def stats(self) -> dict:
        """Operational counters computed directly from the immutable store."""
        with self.engine.connect() as conn:
            total = conn.execute(
                sa.select(sa.func.count()).select_from(T)
            ).scalar_one()
            distinct_subjects = conn.execute(
                sa.select(sa.func.count(sa.distinct(T.c.canonical_subject)))
            ).scalar_one()
            distinct_sources = conn.execute(
                sa.select(sa.func.count(sa.distinct(T.c.source)))
            ).scalar_one()
            label_rows = conn.execute(
                sa.select(T.c.sentiment_label, sa.func.count()).group_by(
                    T.c.sentiment_label
                )
            ).all()
            last_received = conn.execute(
                sa.select(sa.func.max(T.c.received_at))
            ).scalar()
        counts = {label: int(n) for label, n in label_rows}
        return {
            "total_observations": int(total or 0),
            "distinct_subjects": int(distinct_subjects or 0),
            "distinct_sources": int(distinct_sources or 0),
            "label_distribution": {
                "bullish": counts.get("bullish", 0),
                "bearish": counts.get("bearish", 0),
                "neutral": counts.get("neutral", 0),
            },
            "last_received_at": last_received,
        }
