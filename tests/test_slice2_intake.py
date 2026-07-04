"""Slice 2: POST /sentiment intake API (validation, label derivation, dedup)."""

from __future__ import annotations

VALID = {
    "source": "news-nlp-v1",
    "idempotency_key": "news-nlp-v1:2026-07-04:AAPL",
    "subject_type": "ticker",
    "subject": "aapl",
    "sentiment_score": 62.5,
    "confidence": 0.8,
    "source_weight": 0.9,
    "horizon": "1d",
    "reason": "Strong earnings beat with raised guidance",
    "tags": ["earnings", "guidance"],
    "metadata": {"model": "nlp-v1"},
}


class TestIntake:
    def test_accept_returns_201(self, app_client):
        r = app_client.post_json("/sentiment", VALID)
        assert r.status_int == 201
        assert r.json["status"] == "accepted"
        assert r.json["sentiment_label"] == "bullish"  # 62.5 > neutral band (20)
        assert r.json["canonical_subject"] == "AAPL"  # ticker upper-cased
        assert r.json["sentiment_id"]

    def test_label_bearish(self, app_client):
        body = {**VALID, "idempotency_key": "k-bear", "sentiment_score": -55}
        r = app_client.post_json("/sentiment", body)
        assert r.json["sentiment_label"] == "bearish"

    def test_label_neutral_within_band(self, app_client):
        body = {**VALID, "idempotency_key": "k-neutral", "sentiment_score": 5}
        r = app_client.post_json("/sentiment", body)
        assert r.json["sentiment_label"] == "neutral"

    def test_duplicate_idempotency_key_returns_200(self, app_client):
        body = {**VALID, "idempotency_key": "dup-1"}
        first = app_client.post_json("/sentiment", body)
        assert first.status_int == 201
        second = app_client.post_json("/sentiment", body)
        assert second.status_int == 200
        assert second.json["status"] == "duplicate"
        assert second.json["sentiment_id"] == first.json["sentiment_id"]

    def test_observation_is_persisted(self, app_client, repo):
        body = {**VALID, "idempotency_key": "persist-1"}
        r = app_client.post_json("/sentiment", body)
        stored = repo.get_by_id(r.json["sentiment_id"])
        assert stored is not None
        assert stored.source == "news-nlp-v1"
        assert stored.sentiment_label.value == "bullish"

    def test_missing_score_422(self, app_client):
        body = {k: v for k, v in VALID.items() if k != "sentiment_score"}
        body["idempotency_key"] = "k-missing-score"
        r = app_client.post_json("/sentiment", body, expect_errors=True)
        assert r.status_int == 422

    def test_score_out_of_range_422(self, app_client):
        body = {**VALID, "idempotency_key": "k-oor", "sentiment_score": 150}
        r = app_client.post_json("/sentiment", body, expect_errors=True)
        assert r.status_int == 422

    def test_missing_source_422(self, app_client):
        body = {k: v for k, v in VALID.items() if k != "source"}
        body["idempotency_key"] = "k-no-source"
        r = app_client.post_json("/sentiment", body, expect_errors=True)
        assert r.status_int == 422

    def test_invalid_subject_type_422(self, app_client):
        body = {**VALID, "idempotency_key": "k-bad-subject", "subject_type": "crypto"}
        r = app_client.post_json("/sentiment", body, expect_errors=True)
        assert r.status_int == 422

    def test_confidence_out_of_range_422(self, app_client):
        body = {**VALID, "idempotency_key": "k-conf", "confidence": 1.5}
        r = app_client.post_json("/sentiment", body, expect_errors=True)
        assert r.status_int == 422
