"""Time helpers anchored to the container's local timezone.

Every timestamp in this service is stored and returned in the container's local
timezone (configured via the ``TZ`` environment variable, e.g. ``America/New_York``).
Database functions must use this same local time, never UTC or a fixed offset.
"""

from __future__ import annotations

import os
from datetime import datetime, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def local_tz_name() -> str | None:
    """Return the container's configured timezone name (from ``TZ``), if any."""
    return os.environ.get("TZ") or None


def local_tz() -> tzinfo:
    """Return the container's local timezone.

    Prefers the named zone from ``TZ`` (DST-correct across all dates) and falls
    back to the system's configured local timezone when the name is unavailable.
    """
    name = local_tz_name()
    if name:
        try:
            return ZoneInfo(name)
        except ZoneInfoNotFoundError:
            pass
    return datetime.now().astimezone().tzinfo


def now_local() -> datetime:
    """Current time as a timezone-aware datetime in the container's local zone."""
    return datetime.now(local_tz())


def to_local(value) -> datetime | None:
    """Coerce a datetime or ISO string to the container's local timezone.

    Naive values (e.g. from the SQLite test backend) are assumed to already be in
    local time; aware values are converted.
    """
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if value.tzinfo is None:
        return value.replace(tzinfo=local_tz())
    return value.astimezone(local_tz())
