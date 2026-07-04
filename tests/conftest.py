"""Shared pytest fixtures.

Tests run against an in-memory SQLite database (no Docker/PostgreSQL required).
The ``sentiment`` schema is translated to SQLite's default schema, and the
repository's SQLAlchemy Core statements run unchanged against both backends.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from webtest import TestApp

from app import db, dependencies
from app.models.domain import SentimentLabel, SentimentObservation, SubjectType
from app.repository.postgres import SentimentRepository
from app.repository.schema import metadata
from app.services.subject_resolver import SubjectResolver


def make_observation(**overrides) -> SentimentObservation:
    """Build a valid :class:`SentimentObservation` for tests."""
    now = datetime.now(timezone.utc)
    data = dict(
        sentiment_id=uuid4(),
        source="news-nlp-v1",
        idempotency_key="k1",
        subject_type=SubjectType.ticker,
        subject="AAPL",
        canonical_subject="AAPL",
        sentiment_label=SentimentLabel.bullish,
        sentiment_score=42.0,
        confidence=0.8,
        source_weight=1.0,
        horizon="1d",
        market="stocks",
        locale="us",
        reason="test observation",
        tags=["earnings"],
        metadata={"strategy": "nlp-v1"},
        observed_at=now,
        received_at=now,
    )
    data.update(overrides)
    return SentimentObservation(**data)


@pytest.fixture
def make_obs():
    """Expose the observation factory as a fixture."""
    return make_observation


@pytest.fixture(autouse=True)
def _reset_subject_backend():
    """Ensure each test starts with the default (null) resolver backend."""
    SubjectResolver.set_backend(None)
    yield
    SubjectResolver.set_backend(None)


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    ).execution_options(schema_translate_map={"sentiment": None})
    metadata.create_all(eng)
    try:
        yield eng
    finally:
        eng.dispose()


@pytest.fixture
def repo(engine):
    return SentimentRepository(engine)


@pytest.fixture
def app_client(engine):
    """A WebTest client wired to the in-memory database."""
    db.set_engine(engine)
    dependencies.set_repo(SentimentRepository(engine))
    from app.main import create_app

    client = TestApp(create_app())
    try:
        yield client
    finally:
        dependencies.set_repo(None)
        db.set_engine(None)
