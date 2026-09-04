"""Alembic environment for quant_sentiment.

Migrations run against PostgreSQL only (the production system of record). The
database URL is read from the ``DATABASE_URL`` environment variable.

Every object this service owns lives under the dedicated ``sentiment`` schema,
including the Alembic version table (``sentiment.alembic_version_sentiment``).
On startup any project-owned table still sitting in the default ``public``
schema (legacy placement) is relocated into ``sentiment`` with its data intact,
so migration state and stored observations survive the move.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

import sqlalchemy as sa
from alembic import context
from sqlalchemy import create_engine

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None

SCHEMA = "sentiment"
VERSION_TABLE = "alembic_version_sentiment"

# Tables this service owns. Any found in ``public`` (legacy placement) are moved
# under ``SCHEMA`` on startup, preserving their data.
PROJECT_TABLES = ("sentiment_observations", VERSION_TABLE)


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")
    return url


def _relocate_legacy_tables(connection) -> None:
    """Move any project-owned table from ``public`` into ``SCHEMA``.

    Idempotent: tables already under ``SCHEMA`` (or absent) are left untouched.
    ``ALTER TABLE ... SET SCHEMA`` preserves rows, indexes, and constraints.
    """
    connection.execute(sa.text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))
    for table in PROJECT_TABLES:
        in_public = connection.execute(
            sa.text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = :name"
            ),
            {"name": table},
        ).first()
        in_schema = connection.execute(
            sa.text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = :schema AND table_name = :name"
            ),
            {"schema": SCHEMA, "name": table},
        ).first()
        if in_public and not in_schema:
            connection.execute(
                sa.text(f'ALTER TABLE public."{table}" SET SCHEMA {SCHEMA}')
            )


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table=VERSION_TABLE,
        version_table_schema=SCHEMA,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_database_url(), pool_pre_ping=True, future=True)
    with engine.connect() as connection:
        with connection.begin():
            _relocate_legacy_tables(connection)
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table=VERSION_TABLE,
            version_table_schema=SCHEMA,
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
