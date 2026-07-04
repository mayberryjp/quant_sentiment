"""Initial sentiment schema.

Creates the ``sentiment`` schema, the append-only ``sentiment_observations``
table, its indexes, and a defense-in-depth trigger that rejects any UPDATE or
DELETE (sentiment is immutable once stored).

Revision ID: 0001_sentiment
Revises:
Create Date: 2026-07-04

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_sentiment"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS sentiment")

    op.execute(
        """
        CREATE TABLE sentiment.sentiment_observations (
            id                 BIGSERIAL PRIMARY KEY,
            sentiment_id       UUID NOT NULL UNIQUE,
            source             TEXT NOT NULL,
            idempotency_key    TEXT NOT NULL,
            subject_type       TEXT NOT NULL DEFAULT 'ticker',
            subject            TEXT NOT NULL,
            canonical_subject  TEXT NOT NULL,
            sentiment_label    TEXT NOT NULL,
            sentiment_score    DOUBLE PRECISION NOT NULL,
            confidence         DOUBLE PRECISION,
            source_weight      DOUBLE PRECISION,
            horizon            TEXT,
            market             TEXT NOT NULL DEFAULT 'stocks',
            locale             TEXT NOT NULL DEFAULT 'us',
            reason             TEXT NOT NULL DEFAULT '',
            tags               JSONB NOT NULL DEFAULT '[]',
            metadata           JSONB NOT NULL DEFAULT '{}',
            observed_at        TIMESTAMPTZ NOT NULL,
            received_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            schema_version     INTEGER NOT NULL DEFAULT 1,
            CONSTRAINT uq_sentiment_source_idem UNIQUE (source, idempotency_key)
        )
        """
    )

    op.execute(
        "CREATE INDEX ix_sentiment_subject ON sentiment.sentiment_observations "
        "(subject_type, canonical_subject, observed_at DESC)"
    )
    op.execute(
        "CREATE INDEX ix_sentiment_source ON sentiment.sentiment_observations (source)"
    )
    op.execute(
        "CREATE INDEX ix_sentiment_received ON sentiment.sentiment_observations "
        "(received_at DESC)"
    )
    op.execute(
        "CREATE INDEX ix_sentiment_label ON sentiment.sentiment_observations "
        "(sentiment_label)"
    )

    # Defense-in-depth: enforce append-only at the database layer.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION sentiment.reject_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION
                'sentiment_observations is append-only; % is not permitted', TG_OP;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_sentiment_append_only
        BEFORE UPDATE OR DELETE ON sentiment.sentiment_observations
        FOR EACH ROW EXECUTE FUNCTION sentiment.reject_mutation()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_sentiment_append_only "
        "ON sentiment.sentiment_observations"
    )
    op.execute("DROP TABLE IF EXISTS sentiment.sentiment_observations CASCADE")
    op.execute("DROP FUNCTION IF EXISTS sentiment.reject_mutation()")
    # The schema itself is left in place; it may be shared with sibling services.
