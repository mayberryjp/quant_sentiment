"""Slice 6: health, readiness, and operational stats."""

from __future__ import annotations


def _post(client, **overrides):
    body = {
        "source": "srcA",
        "idempotency_key": "k",
        "subject_type": "ticker",
        "subject": "AAPL",
        "sentiment_score": 50,
    }
    body.update(overrides)
    return client.post_json("/sentiment", body)


class TestHealth:
    def test_health_ok(self, app_client):
        r = app_client.get("/sentiment/health")
        assert r.status_int == 200
        assert r.json["status"] == "ok"

    def test_ready_ok(self, app_client):
        r = app_client.get("/sentiment/ready")
        assert r.status_int == 200
        assert r.json["status"] == "ready"
        assert r.json["database"] == "ok"


class TestStats:
    def test_stats_empty(self, app_client):
        r = app_client.get("/sentiment/stats")
        assert r.status_int == 200
        assert r.json["total_observations"] == 0
        assert r.json["distinct_subjects"] == 0
        assert r.json["distinct_sources"] == 0
        assert r.json["label_distribution"] == {"bullish": 0, "bearish": 0, "neutral": 0}
        assert r.json["last_received_at"] is None

    def test_stats_after_posts(self, app_client):
        _post(app_client, idempotency_key="1", source="srcA", subject="AAPL", sentiment_score=60)
        _post(app_client, idempotency_key="2", source="srcB", subject="MSFT", sentiment_score=-60)
        _post(app_client, idempotency_key="3", source="srcA", subject="AAPL", sentiment_score=0)
        r = app_client.get("/sentiment/stats")
        assert r.json["total_observations"] == 3
        assert r.json["distinct_subjects"] == 2  # AAPL, MSFT
        assert r.json["distinct_sources"] == 2  # srcA, srcB
        assert r.json["label_distribution"] == {"bullish": 1, "bearish": 1, "neutral": 1}
        assert r.json["last_received_at"] is not None
