"""Sentiment intake + read routes (Slices 2 & 4)."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from bottle import Bottle, HTTPError, HTTPResponse, request, response
from pydantic import ValidationError

from app.config import settings
from app.dependencies import get_repo
from app.models.requests import SentimentSubmission
from app.models.responses import (
    SentimentAcceptedResponse,
    SentimentDetailResponse,
    SentimentListResponse,
)
from app.services.sentiment_service import ingest_observation

sub = Bottle()

UUID_RE = (
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


def _detail(obs) -> SentimentDetailResponse:
    return SentimentDetailResponse(**obs.model_dump(mode="json"))


def _parse_utc(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _validation_error(exc: ValidationError) -> HTTPResponse:
    return HTTPResponse(
        status=422,
        body=json.dumps({"detail": json.loads(exc.json())}),
        content_type="application/json",
    )


@sub.post("/sentiment")
def submit_sentiment():
    try:
        payload = request.json
    except (HTTPError, ValueError, TypeError):
        raise HTTPResponse(
            status=422,
            body=json.dumps({"detail": "request body must be valid JSON"}),
            content_type="application/json",
        )
    try:
        body = SentimentSubmission(**(payload or {}))
    except ValidationError as exc:
        raise _validation_error(exc)

    observation, is_duplicate = ingest_observation(body, get_repo())
    result = SentimentAcceptedResponse(
        status="duplicate" if is_duplicate else "accepted",
        sentiment_id=observation.sentiment_id,
        sentiment_label=observation.sentiment_label.value,
        subject_type=observation.subject_type.value,
        canonical_subject=observation.canonical_subject,
    )
    response.status = 200 if is_duplicate else 201
    return result.model_dump(mode="json")


@sub.get("/sentiment/recent")
def recent_sentiment():
    params = request.params
    try:
        since = _parse_utc(params.get("since")) if params.get("since") else None
        until = _parse_utc(params.get("until")) if params.get("until") else None
    except ValueError:
        raise HTTPResponse(
            status=422,
            body=json.dumps({"detail": "since/until must be ISO-8601 datetimes"}),
            content_type="application/json",
        )
    try:
        page = max(int(params.get("page", 1)), 1)
        page_size = int(params.get("page_size", settings.default_page_size))
    except ValueError:
        raise HTTPResponse(
            status=422,
            body=json.dumps({"detail": "page/page_size must be integers"}),
            content_type="application/json",
        )
    page_size = max(1, min(page_size, settings.max_page_size))

    items, total = get_repo().list_observations(
        source=params.get("source"),
        subject=params.get("subject"),
        subject_type=params.get("subject_type"),
        sentiment_label=params.get("sentiment_label"),
        market=params.get("market"),
        locale=params.get("locale"),
        since=since,
        until=until,
        page=page,
        page_size=page_size,
    )
    result = SentimentListResponse(
        items=[_detail(o) for o in items],
        total=total,
        page=page,
        page_size=page_size,
    )
    return result.model_dump(mode="json")


@sub.get("/sentiment/by-subject/<subject>")
def sentiment_by_subject(subject):
    params = request.params
    try:
        limit = int(params.get("limit", 100))
    except ValueError:
        limit = 100
    limit = max(1, min(limit, 500))
    items = get_repo().get_by_subject(
        subject, subject_type=params.get("subject_type"), limit=limit
    )
    data = [_detail(o).model_dump(mode="json") for o in items]
    response.content_type = "application/json"
    return json.dumps(data)


@sub.get(f"/sentiment/<sentiment_id:re:{UUID_RE}>")
def get_sentiment(sentiment_id):
    obs = get_repo().get_by_id(sentiment_id)
    if obs is None:
        raise HTTPResponse(
            status=404,
            body=json.dumps({"detail": "sentiment observation not found"}),
            content_type="application/json",
        )
    return _detail(obs).model_dump(mode="json")
