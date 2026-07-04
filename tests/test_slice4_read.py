"""Slice 4: read API — recent (filters + pagination), by id, by subject."""

from __future__ import annotations

from uuid import uuid4


def _post(client, **overrides):
    body = {
        "source": "news-nlp-v1",
        "idempotency_key": "k",
        "subject_type": "ticker",
        "subject": "AAPL",
        "sentiment_score": 50,
    }
    body.update(overrides)
    return client.post_json("/sentiment", body)


class TestRecent:
    def test_empty(self, app_client):
        r = app_client.get("/sentiment/recent")
        assert r.status_int == 200
        assert r.json["items"] == []
        assert r.json["total"] == 0

    def test_after_post(self, app_client):
        _post(app_client, idempotency_key="a")
        r = app_client.get("/sentiment/recent")
        assert r.json["total"] == 1
        assert r.json["items"][0]["subject"] == "AAPL"
        assert r.json["items"][0]["sentiment_label"] == "bullish"

    def test_filter_by_source(self, app_client):
        _post(app_client, idempotency_key="a", source="src-a")
        _post(app_client, idempotency_key="b", source="src-b")
        r = app_client.get("/sentiment/recent", {"source": "src-a"})
        assert r.json["total"] == 1
        assert r.json["items"][0]["source"] == "src-a"

    def test_filter_by_subject_case_insensitive(self, app_client):
        _post(app_client, idempotency_key="a", subject="AAPL")
        r = app_client.get("/sentiment/recent", {"subject": "aapl"})
        assert r.json["total"] == 1

    def test_filter_by_label(self, app_client):
        _post(app_client, idempotency_key="bull", sentiment_score=80)
        _post(app_client, idempotency_key="bear", sentiment_score=-80)
        r = app_client.get("/sentiment/recent", {"sentiment_label": "bearish"})
        assert r.json["total"] == 1
        assert r.json["items"][0]["sentiment_label"] == "bearish"

    def test_pagination(self, app_client):
        for i in range(5):
            _post(app_client, idempotency_key=f"k{i}")
        r1 = app_client.get("/sentiment/recent", {"page": 1, "page_size": 2})
        assert len(r1.json["items"]) == 2
        assert r1.json["total"] == 5
        r3 = app_client.get("/sentiment/recent", {"page": 3, "page_size": 2})
        assert len(r3.json["items"]) == 1

    def test_invalid_since_returns_422(self, app_client):
        r = app_client.get(
            "/sentiment/recent", {"since": "not-a-date"}, expect_errors=True
        )
        assert r.status_int == 422


class TestGetById:
    def test_found(self, app_client):
        posted = _post(app_client, idempotency_key="a")
        sid = posted.json["sentiment_id"]
        r = app_client.get(f"/sentiment/{sid}")
        assert r.status_int == 200
        assert r.json["sentiment_id"] == sid
        assert r.json["source"] == "news-nlp-v1"
        assert r.json["schema_version"] == 1

    def test_not_found(self, app_client):
        r = app_client.get(f"/sentiment/{uuid4()}", expect_errors=True)
        assert r.status_int == 404


class TestBySubject:
    def test_returns_list(self, app_client):
        _post(app_client, idempotency_key="a", subject="AAPL")
        _post(app_client, idempotency_key="b", subject="AAPL")
        _post(app_client, idempotency_key="c", subject="MSFT")
        r = app_client.get("/sentiment/by-subject/AAPL")
        assert r.status_int == 200
        assert isinstance(r.json, list)
        assert len(r.json) == 2

    def test_empty(self, app_client):
        r = app_client.get("/sentiment/by-subject/ZZZZ")
        assert r.json == []
