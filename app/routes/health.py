"""Health, readiness, and operational-visibility routes (Slices 0 & 6)."""

from __future__ import annotations

from bottle import Bottle, response

from app.dependencies import get_repo
from app.timeutil import to_utc

sub = Bottle()


@sub.get("/sentiment/health")
def health():
    """Liveness probe. Does not depend on the database."""
    return {"status": "ok"}


@sub.get("/sentiment/ready")
def ready():
    """Readiness probe. Fails (503) when the database is unreachable."""
    database_ok = get_repo().ping()
    if not database_ok:
        response.status = 503
    return {
        "status": "ready" if database_ok else "not_ready",
        "database": "ok" if database_ok else "unavailable",
    }


@sub.get("/sentiment/stats")
def stats():
    """Operational counters computed from the immutable observation store."""
    data = get_repo().stats()
    last_received = to_utc(data["last_received_at"])
    return {
        "total_observations": data["total_observations"],
        "distinct_subjects": data["distinct_subjects"],
        "distinct_sources": data["distinct_sources"],
        "label_distribution": data["label_distribution"],
        "last_received_at": last_received.isoformat() if last_received else None,
    }
