"""Duration parsing for aggregation windows and time-series buckets.

Accepts compact strings like ``1h``, ``4h``, ``1d``, ``7d``, ``30d`` or ``2w``.
"""

from __future__ import annotations

import re
from datetime import timedelta

_PATTERN = re.compile(r"^(\d+)([hdw])$")
_UNITS = {"h": "hours", "d": "days", "w": "weeks"}


def parse_duration(text: str) -> timedelta:
    match = _PATTERN.match((text or "").strip().lower())
    if not match:
        raise ValueError(f"invalid duration '{text}' (use e.g. 1h, 4h, 1d, 7d, 30d)")
    quantity = int(match.group(1))
    if quantity <= 0:
        raise ValueError("duration must be positive")
    return timedelta(**{_UNITS[match.group(2)]: quantity})
