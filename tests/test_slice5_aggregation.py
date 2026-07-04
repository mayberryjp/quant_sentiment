"""Slice 5: aggregation API (single-window aggregate + time-series buckets)."""

from __future__ import annotations


def _post(client, **overrides):
    body = {
        "source": "srcA",
        "idempotency_key": "k",
        "subject_type": "ticker",
        "subject": "AAPL",
        "sentiment_score": 50,
        "confidence": 1.0,
        "source_weight": 1.0,
    }
    body.update(overrides)
    return client.post_json("/sentiment", body)


class TestAggregate:
    def test_empty(self, app_client):
        r = app_client.get("/sentiment/aggregate", {"subject": "AAPL"})
        assert r.status_int == 200
        assert r.json["count"] == 0
        assert r.json["mean_score"] is None
        assert r.json["confidence_weighted_score"] is None
        assert r.json["net_label"] is None
        assert r.json["label_distribution"] == {"bullish": 0, "bearish": 0, "neutral": 0}

    def test_basic_aggregate_math(self, app_client):
        _post(app_client, idempotency_key="1", sentiment_score=60, confidence=1.0, source_weight=1.0)
        _post(app_client, idempotency_key="2", sentiment_score=-40, confidence=0.5, source_weight=1.0)
        _post(app_client, idempotency_key="3", sentiment_score=0, confidence=None, source_weight=None)
        d = app_client.get("/sentiment/aggregate", {"subject": "aapl"}).json
        assert d["count"] == 3
        assert abs(d["mean_score"] - (20 / 3)) < 1e-6
        # weighted = (60*1 + -40*0.5 + 0*1) / (1 + 0.5 + 1) = 40 / 2.5 = 16
        assert abs(d["confidence_weighted_score"] - 16.0) < 1e-6
        assert d["label_distribution"] == {"bullish": 1, "bearish": 1, "neutral": 1}
        assert d["net_label"] == "neutral"  # |16| <= neutral band (20)
        assert d["sources"] == ["srcA"]
        assert d["subject"] == "AAPL"
        assert d["window"] == "1d"

    def test_filter_by_source(self, app_client):
        _post(app_client, idempotency_key="1", source="srcA", sentiment_score=60)
        _post(app_client, idempotency_key="2", source="srcB", sentiment_score=-60)
        d = app_client.get("/sentiment/aggregate", {"subject": "AAPL", "source": "srcA"}).json
        assert d["count"] == 1
        assert d["net_label"] == "bullish"

    def test_min_confidence_excludes_low_and_null(self, app_client):
        _post(app_client, idempotency_key="1", sentiment_score=60, confidence=0.9)
        _post(app_client, idempotency_key="2", sentiment_score=-60, confidence=0.2)
        d = app_client.get(
            "/sentiment/aggregate", {"subject": "AAPL", "min_confidence": 0.5}
        ).json
        assert d["count"] == 1

    def test_invalid_window_422(self, app_client):
        r = app_client.get(
            "/sentiment/aggregate", {"subject": "AAPL", "window": "xyz"}, expect_errors=True
        )
        assert r.status_int == 422

    def test_window_exceeds_max_422(self, app_client):
        r = app_client.get(
            "/sentiment/aggregate", {"subject": "AAPL", "window": "999d"}, expect_errors=True
        )
        assert r.status_int == 422

    def test_invalid_time_basis_422(self, app_client):
        r = app_client.get(
            "/sentiment/aggregate",
            {"subject": "AAPL", "time_basis": "bogus"},
            expect_errors=True,
        )
        assert r.status_int == 422

    def test_missing_subject_422(self, app_client):
        r = app_client.get("/sentiment/aggregate", expect_errors=True)
        assert r.status_int == 422


class TestTimeseries:
    def test_buckets_returned(self, app_client):
        _post(app_client, idempotency_key="1", sentiment_score=60)
        d = app_client.get(
            "/sentiment/aggregate/timeseries",
            {"subject": "AAPL", "window": "1d", "bucket": "1h"},
        ).json
        assert d["bucket"] == "1h"
        assert len(d["buckets"]) == 24
        assert sum(b["count"] for b in d["buckets"]) == 1

    def test_too_many_buckets_422(self, app_client):
        r = app_client.get(
            "/sentiment/aggregate/timeseries",
            {"subject": "AAPL", "window": "90d", "bucket": "1h"},
            expect_errors=True,
        )
        assert r.status_int == 422
