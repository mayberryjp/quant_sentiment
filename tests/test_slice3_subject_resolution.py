"""Slice 3: subject normalization and pluggable ticker resolution."""

from __future__ import annotations

from app.models.domain import SubjectType
from app.services.subject_resolver import SubjectResolver, canonicalize_subject


class _AliasBackend:
    """Maps a couple of canonical tickers to their master form."""

    def resolve_ticker(self, ticker: str, market: str, locale: str) -> str | None:
        return {"BRK.B": "BRK-B"}.get(ticker)


class _FailingBackend:
    def resolve_ticker(self, ticker: str, market: str, locale: str) -> str | None:
        raise RuntimeError("symbol master unavailable")


class TestCanonicalization:
    def test_ticker_uppercased_and_trimmed(self):
        assert canonicalize_subject(SubjectType.ticker, "  aapl ") == "AAPL"

    def test_sector_lowercased(self):
        assert canonicalize_subject(SubjectType.sector, " Technology ") == "technology"

    def test_theme_lowercased(self):
        assert canonicalize_subject(SubjectType.theme, "AI Infrastructure") == "ai infrastructure"

    def test_market_uppercased(self):
        assert canonicalize_subject(SubjectType.market, "spx") == "SPX"


class TestResolver:
    def test_default_backend_falls_back_to_canonical(self):
        assert SubjectResolver.resolve(SubjectType.ticker, "aapl") == "AAPL"

    def test_backend_refines_ticker(self):
        SubjectResolver.set_backend(_AliasBackend())
        assert SubjectResolver.resolve(SubjectType.ticker, "brk.b") == "BRK-B"

    def test_backend_miss_uses_canonical(self):
        SubjectResolver.set_backend(_AliasBackend())
        assert SubjectResolver.resolve(SubjectType.ticker, "aapl") == "AAPL"

    def test_backend_ignored_for_non_ticker(self):
        SubjectResolver.set_backend(_AliasBackend())
        assert SubjectResolver.resolve(SubjectType.sector, "Technology") == "technology"

    def test_backend_failure_is_graceful(self):
        SubjectResolver.set_backend(_FailingBackend())
        assert SubjectResolver.resolve(SubjectType.ticker, "aapl") == "AAPL"


class TestResolutionViaAPI:
    def test_intake_uses_resolver(self, app_client):
        SubjectResolver.set_backend(_AliasBackend())
        body = {
            "source": "s",
            "idempotency_key": "r1",
            "subject_type": "ticker",
            "subject": "brk.b",
            "sentiment_score": 30,
        }
        r = app_client.post_json("/sentiment", body)
        assert r.status_int == 201
        assert r.json["canonical_subject"] == "BRK-B"

    def test_intake_graceful_on_backend_failure(self, app_client):
        SubjectResolver.set_backend(_FailingBackend())
        body = {
            "source": "s",
            "idempotency_key": "r2",
            "subject_type": "ticker",
            "subject": "nvda",
            "sentiment_score": 30,
        }
        r = app_client.post_json("/sentiment", body)
        assert r.status_int == 201  # observation still stored
        assert r.json["canonical_subject"] == "NVDA"
