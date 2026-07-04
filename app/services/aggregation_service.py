"""Aggregation service — the core value-add of the sentiment aggregator.

Computes read-time aggregates for a subject over a time window (and, optionally,
over evenly-spaced buckets). Uses parameterized SQL for the single-window
aggregate; time-series bucketing is done in Python for backend portability.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

from app.config import settings
from app.repository.postgres import SentimentRepository
from app.services.labels import derive_label
from app.services.subject_resolver import canonicalize_subject
from app.services.windows import parse_duration

_MAX_BUCKETS = 1000
_VALID_TIME_BASIS = {"observed_at", "received_at"}


def _to_utc(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _weight(confidence, source_weight) -> float:
    return (1.0 if confidence is None else confidence) * (
        1.0 if source_weight is None else source_weight
    )


def _net_label(weighted_score, mean_score):
    basis = weighted_score if weighted_score is not None else mean_score
    if basis is None:
        return None
    return derive_label(basis).value


def _validate_common(window: str | None, time_basis: str):
    if time_basis not in _VALID_TIME_BASIS:
        raise ValueError("time_basis must be 'observed_at' or 'received_at'")
    window = window or settings.default_window
    wdelta = parse_duration(window)  # raises ValueError if malformed
    if wdelta > parse_duration(settings.max_window):
        raise ValueError(f"window exceeds maximum of {settings.max_window}")
    return window, wdelta


def aggregate(
    repo: SentimentRepository,
    *,
    subject: str,
    subject_type: str = "ticker",
    window: str | None = None,
    source: str | None = None,
    min_confidence: float | None = None,
    time_basis: str = "observed_at",
) -> dict:
    window, wdelta = _validate_common(window, time_basis)
    now = datetime.now(timezone.utc)
    since = now - wdelta
    canonical = canonicalize_subject(_subject_type_enum(subject_type), subject)

    raw = repo.aggregate(
        canonical_subject=canonical,
        subject_type=subject_type,
        source=source,
        min_confidence=min_confidence,
        time_basis=time_basis,
        since=since,
    )
    weighted_score = (
        raw["weighted_sum"] / raw["weight_sum"]
        if raw["weight_sum"]
        else None
    )
    label_counts = raw["label_counts"]
    return {
        "subject": canonical,
        "subject_type": subject_type,
        "window": window,
        "time_basis": time_basis,
        "from": since.isoformat(),
        "to": now.isoformat(),
        "count": raw["count"],
        "mean_score": raw["mean_score"],
        "confidence_weighted_score": weighted_score,
        "label_distribution": {
            "bullish": label_counts.get("bullish", 0),
            "bearish": label_counts.get("bearish", 0),
            "neutral": label_counts.get("neutral", 0),
        },
        "net_label": _net_label(weighted_score, raw["mean_score"]),
        "sources": raw["sources"],
        "latest_observed_at": (
            dt.isoformat() if (dt := _to_utc(raw["latest"])) else None
        ),
    }


def timeseries(
    repo: SentimentRepository,
    *,
    subject: str,
    subject_type: str = "ticker",
    window: str | None = None,
    bucket: str | None = None,
    source: str | None = None,
    min_confidence: float | None = None,
    time_basis: str = "observed_at",
) -> dict:
    window, wdelta = _validate_common(window, time_basis)
    bdelta = parse_duration(bucket or "1h")
    n_buckets = math.ceil(wdelta / bdelta)
    if n_buckets > _MAX_BUCKETS:
        raise ValueError(
            f"too many buckets ({n_buckets}); widen the bucket or narrow the window"
        )

    now = datetime.now(timezone.utc)
    since = now - wdelta
    canonical = canonicalize_subject(_subject_type_enum(subject_type), subject)

    rows = repo.fetch_window_rows(
        canonical_subject=canonical,
        subject_type=subject_type,
        source=source,
        min_confidence=min_confidence,
        time_basis=time_basis,
        since=since,
    )

    buckets = [
        {"scores": [], "weighted_sum": 0.0, "weight_sum": 0.0,
         "labels": {"bullish": 0, "bearish": 0, "neutral": 0}}
        for _ in range(n_buckets)
    ]
    for row in rows:
        t = _to_utc(row["t"])
        if t is None:
            continue
        index = int((t - since) / bdelta)
        index = min(max(index, 0), n_buckets - 1)
        b = buckets[index]
        b["scores"].append(row["score"])
        w = _weight(row["confidence"], row["source_weight"])
        b["weighted_sum"] += row["score"] * w
        b["weight_sum"] += w
        label = row["label"]
        if label in b["labels"]:
            b["labels"][label] += 1

    out_buckets = []
    for i, b in enumerate(buckets):
        b_start = since + i * bdelta
        count = len(b["scores"])
        mean = sum(b["scores"]) / count if count else None
        weighted = b["weighted_sum"] / b["weight_sum"] if b["weight_sum"] else None
        out_buckets.append(
            {
                "from": b_start.isoformat(),
                "to": (b_start + bdelta).isoformat(),
                "count": count,
                "mean_score": mean,
                "confidence_weighted_score": weighted,
                "label_distribution": b["labels"],
                "net_label": _net_label(weighted, mean),
            }
        )

    return {
        "subject": canonical,
        "subject_type": subject_type,
        "window": window,
        "bucket": bucket or "1h",
        "time_basis": time_basis,
        "from": since.isoformat(),
        "to": now.isoformat(),
        "buckets": out_buckets,
    }


def _subject_type_enum(subject_type: str):
    # Local import avoids a module-level cycle and keeps canonicalization shared.
    from app.models.domain import SubjectType

    try:
        return SubjectType(subject_type)
    except ValueError:
        return SubjectType.ticker
