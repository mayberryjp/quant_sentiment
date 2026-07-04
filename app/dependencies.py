"""Dependency wiring shared by route handlers.

Handlers call :func:`get_repo`; tests swap the implementation with
:func:`set_repo` so no live database is required.
"""

from __future__ import annotations

from app.db import get_engine
from app.repository.postgres import SentimentRepository

_repo: SentimentRepository | None = None


def get_repo() -> SentimentRepository:
    global _repo
    if _repo is None:
        _repo = SentimentRepository(get_engine())
    return _repo


def set_repo(repo: SentimentRepository | None) -> None:
    """Override (or clear) the process-wide repository. Used by tests."""
    global _repo
    _repo = repo
