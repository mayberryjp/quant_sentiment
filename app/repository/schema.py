"""Authoritative SQLAlchemy Core table definitions for the sentiment store.

These tables are the single source of truth used by the repository. In
production they map onto the PostgreSQL ``sentiment`` schema created by Alembic
migration ``0001_sentiment``. In tests they are created on SQLite via
``metadata.create_all`` with a schema-translate map, so identical code paths
exercise both backends.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

metadata = sa.MetaData(schema="sentiment")

# Portable JSON column: JSONB on PostgreSQL, generic JSON elsewhere (SQLite).
JSON_VARIANT = sa.JSON().with_variant(JSONB(), "postgresql")

sentiment_observations = sa.Table(
    "sentiment_observations",
    metadata,
    # BIGINT on PostgreSQL (BIGSERIAL via Alembic); INTEGER on SQLite so the
    # test backend auto-increments the surrogate primary key.
    sa.Column(
        "id",
        sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
        primary_key=True,
        autoincrement=True,
    ),
    sa.Column("sentiment_id", sa.Uuid(as_uuid=True), nullable=False, unique=True),
    sa.Column("source", sa.Text, nullable=False),
    sa.Column("idempotency_key", sa.Text, nullable=False),
    sa.Column("subject_type", sa.Text, nullable=False, server_default="ticker"),
    sa.Column("subject", sa.Text, nullable=False),
    sa.Column("canonical_subject", sa.Text, nullable=False),
    sa.Column("sentiment_label", sa.Text, nullable=False),
    sa.Column("sentiment_score", sa.Float, nullable=False),
    sa.Column("confidence", sa.Float, nullable=True),
    sa.Column("source_weight", sa.Float, nullable=True),
    sa.Column("horizon", sa.Text, nullable=True),
    sa.Column("market", sa.Text, nullable=False, server_default="stocks"),
    sa.Column("locale", sa.Text, nullable=False, server_default="us"),
    sa.Column("reason", sa.Text, nullable=False, server_default=""),
    sa.Column("tags", JSON_VARIANT, nullable=False),
    sa.Column("metadata", JSON_VARIANT, nullable=False),
    sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("schema_version", sa.Integer, nullable=False, server_default="1"),
    sa.UniqueConstraint("source", "idempotency_key", name="uq_sentiment_source_idem"),
    sa.Index("ix_sentiment_subject", "subject_type", "canonical_subject", "observed_at"),
    sa.Index("ix_sentiment_source", "source"),
    sa.Index("ix_sentiment_received", "received_at"),
    sa.Index("ix_sentiment_label", "sentiment_label"),
)
