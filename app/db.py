"""SQLAlchemy engine helpers.

The engine is created lazily from ``DATABASE_URL``. Tests inject their own
engine (typically SQLite) via :func:`set_engine`, so nothing here assumes
PostgreSQL is reachable.
"""

from __future__ import annotations

import os

from psycopg import sql
from sqlalchemy import Engine, create_engine, event

from app.timeutil import local_tz_name

_engine: Engine | None = None


def get_engine() -> Engine:
    """Return the process-wide engine, creating it from DATABASE_URL if needed."""
    global _engine
    if _engine is not None:
        return _engine
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")
    _engine = create_engine(url, pool_pre_ping=True, future=True)
    if _engine.dialect.name == "postgresql":
        _bind_local_timezone(_engine)
    return _engine


def _bind_local_timezone(engine: Engine) -> None:
    """Pin every PostgreSQL session to the container's local timezone so that
    ``now()`` and returned TIMESTAMPTZ values use local time, not UTC."""
    tz = local_tz_name()
    if not tz:
        return

    @event.listens_for(engine, "connect")
    def _set_timezone(dbapi_conn, _record):  # noqa: ANN001
        # SET TIME ZONE does not accept bind parameters; inline the value safely.
        with dbapi_conn.cursor() as cur:
            cur.execute(sql.SQL("SET TIME ZONE {}").format(sql.Literal(tz)))



def set_engine(engine: Engine | None) -> None:
    """Override (or clear) the process-wide engine. Used by tests."""
    global _engine
    _engine = engine
