"""Subject normalization and resolution.

Two layers:

* :func:`canonicalize_subject` — pure string normalization (always applied).
* :class:`SubjectResolver` — an optional, pluggable symbol-master backend for
  ``ticker`` subjects. Resolution refines the canonical subject (e.g. mapping an
  alias to its canonical ticker). It **degrades gracefully**: if no backend is
  configured, or the backend errors, the observation is still stored using the
  canonicalized subject — sentiment intake is never rejected on resolution.
"""

from __future__ import annotations

import logging
from typing import Protocol

from app.models.domain import SubjectType

log = logging.getLogger("quant_sentiment.subject_resolver")


def canonicalize_subject(subject_type: SubjectType, subject: str) -> str:
    """Return a normalized form of ``subject`` for indexing and aggregation.

    Tickers and market identifiers are upper-cased; sectors and themes are
    lower-cased. Surrounding whitespace is always stripped.
    """
    normalized = subject.strip()
    if subject_type in (SubjectType.ticker, SubjectType.market):
        return normalized.upper()
    return normalized.lower()


class SubjectBackend(Protocol):
    """A symbol-master backend that maps a ticker to its canonical form."""

    def resolve_ticker(self, ticker: str, market: str, locale: str) -> str | None:
        ...


class _NullBackend:
    """Default backend used when no symbol master is configured."""

    def resolve_ticker(self, ticker: str, market: str, locale: str) -> str | None:
        return None


_backend: SubjectBackend = _NullBackend()


class SubjectResolver:
    """Resolves a subject to its canonical form via a pluggable backend."""

    @classmethod
    def set_backend(cls, backend: SubjectBackend | None) -> None:
        global _backend
        _backend = backend or _NullBackend()

    @classmethod
    def resolve(
        cls,
        subject_type: SubjectType,
        subject: str,
        market: str = "stocks",
        locale: str = "us",
    ) -> str:
        canonical = canonicalize_subject(subject_type, subject)
        if subject_type is not SubjectType.ticker:
            return canonical
        try:
            resolved = _backend.resolve_ticker(canonical, market, locale)
        except Exception:  # noqa: BLE001 - resolution must never break intake
            log.warning(
                "ticker resolver backend failed for %s; storing unresolved",
                canonical,
                exc_info=True,
            )
            return canonical
        return resolved or canonical
