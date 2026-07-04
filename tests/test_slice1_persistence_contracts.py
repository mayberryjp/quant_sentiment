"""Slice 1: persistence contracts, domain model, repository, dedup, immutability."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from app.models.domain import SentimentLabel, SentimentObservation, SubjectType


class TestDomainModel:
    def test_json_round_trip(self, make_obs):
        obs = make_obs()
        restored = SentimentObservation.model_validate_json(obs.model_dump_json())
        assert restored.sentiment_id == obs.sentiment_id
        assert restored.sentiment_score == 42.0
        assert restored.subject_type is SubjectType.ticker
        assert restored.sentiment_label is SentimentLabel.bullish

    def test_naive_datetime_coerced_to_utc(self, make_obs):
        obs = make_obs(observed_at=datetime(2026, 1, 1, 12, 0, 0))
        assert obs.observed_at.tzinfo is not None
        assert obs.observed_at.utcoffset().total_seconds() == 0


class TestRepository:
    def test_insert_and_get_by_id(self, repo, make_obs):
        obs = make_obs()
        stored, is_dup = repo.insert_observation(obs)
        assert is_dup is False
        assert stored.sentiment_id == obs.sentiment_id

        fetched = repo.get_by_id(obs.sentiment_id)
        assert fetched is not None
        assert fetched.subject == "AAPL"
        assert fetched.tags == ["earnings"]
        assert fetched.metadata == {"strategy": "nlp-v1"}
        assert fetched.sentiment_score == 42.0
        assert fetched.observed_at.tzinfo is not None

    def test_get_by_id_accepts_string_uuid(self, repo, make_obs):
        obs = make_obs()
        repo.insert_observation(obs)
        assert repo.get_by_id(str(obs.sentiment_id)) is not None

    def test_get_by_source_and_key(self, repo, make_obs):
        obs = make_obs(source="s1", idempotency_key="abc")
        repo.insert_observation(obs)
        found = repo.get_by_source_and_key("s1", "abc")
        assert found is not None
        assert found.sentiment_id == obs.sentiment_id

    def test_dedup_returns_existing_record(self, repo, make_obs):
        first = make_obs(source="s1", idempotency_key="dup", sentiment_score=42.0)
        _, dup1 = repo.insert_observation(first)
        assert dup1 is False

        # Same (source, idempotency_key) but a different payload/id -> duplicate.
        second = make_obs(source="s1", idempotency_key="dup", sentiment_score=-10.0)
        stored2, dup2 = repo.insert_observation(second)
        assert dup2 is True
        assert stored2.sentiment_id == first.sentiment_id  # original preserved
        assert stored2.sentiment_score == 42.0  # never overwritten (append-only)

    def test_get_by_id_missing(self, repo):
        assert repo.get_by_id(uuid4()) is None

    def test_get_by_id_invalid_uuid(self, repo):
        assert repo.get_by_id("not-a-uuid") is None

    def test_repository_has_no_mutation_surface(self, repo):
        assert not hasattr(repo, "update_observation")
        assert not hasattr(repo, "delete_observation")
