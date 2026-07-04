"""Slice 7: validation boundaries and hardening."""

from __future__ import annotations

BASE = {
    "source": "s",
    "idempotency_key": "k",
    "subject_type": "ticker",
    "subject": "AAPL",
    "sentiment_score": 50,
}


class TestValidationBoundaries:
    def test_score_below_min(self, app_client):
        body = {**BASE, "idempotency_key": "a", "sentiment_score": -100.1}
        assert app_client.post_json("/sentiment", body, expect_errors=True).status_int == 422

    def test_score_above_max(self, app_client):
        body = {**BASE, "idempotency_key": "b", "sentiment_score": 100.1}
        assert app_client.post_json("/sentiment", body, expect_errors=True).status_int == 422

    def test_score_at_bounds_ok(self, app_client):
        low = {**BASE, "idempotency_key": "low", "sentiment_score": -100}
        high = {**BASE, "idempotency_key": "high", "sentiment_score": 100}
        assert app_client.post_json("/sentiment", low).status_int == 201
        assert app_client.post_json("/sentiment", high).status_int == 201

    def test_empty_source(self, app_client):
        body = {**BASE, "idempotency_key": "c", "source": ""}
        assert app_client.post_json("/sentiment", body, expect_errors=True).status_int == 422

    def test_empty_idempotency_key(self, app_client):
        body = {**BASE, "idempotency_key": ""}
        assert app_client.post_json("/sentiment", body, expect_errors=True).status_int == 422

    def test_subject_too_long(self, app_client):
        body = {**BASE, "idempotency_key": "d", "subject": "A" * 65}
        assert app_client.post_json("/sentiment", body, expect_errors=True).status_int == 422

    def test_reason_too_long(self, app_client):
        body = {**BASE, "idempotency_key": "e", "reason": "x" * 2001}
        assert app_client.post_json("/sentiment", body, expect_errors=True).status_int == 422

    def test_too_many_tags(self, app_client):
        body = {**BASE, "idempotency_key": "f", "tags": [f"t{i}" for i in range(21)]}
        assert app_client.post_json("/sentiment", body, expect_errors=True).status_int == 422

    def test_metadata_too_large(self, app_client):
        body = {**BASE, "idempotency_key": "g", "metadata": {"blob": "a" * 17000}}
        assert app_client.post_json("/sentiment", body, expect_errors=True).status_int == 422

    def test_confidence_out_of_range(self, app_client):
        body = {**BASE, "idempotency_key": "h", "confidence": 1.5}
        assert app_client.post_json("/sentiment", body, expect_errors=True).status_int == 422

    def test_source_weight_out_of_range(self, app_client):
        body = {**BASE, "idempotency_key": "i", "source_weight": -0.1}
        assert app_client.post_json("/sentiment", body, expect_errors=True).status_int == 422

    def test_malformed_json_returns_422(self, app_client):
        r = app_client.post(
            "/sentiment",
            "{not valid json",
            headers={"Content-Type": "application/json"},
            expect_errors=True,
        )
        assert r.status_int == 422


class TestErrorEnvelopes:
    def test_unknown_route_returns_json_404(self, app_client):
        r = app_client.get("/does-not-exist", expect_errors=True)
        assert r.status_int == 404
        assert r.json["detail"] == "not found"
