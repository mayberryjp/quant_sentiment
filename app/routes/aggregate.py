"""Aggregation routes (Slice 5)."""

from __future__ import annotations

import json

from bottle import Bottle, HTTPResponse, request

from app.dependencies import get_repo
from app.services import aggregation_service

sub = Bottle()


def _error(status: int, detail: str) -> HTTPResponse:
    return HTTPResponse(
        status=status,
        body=json.dumps({"detail": detail}),
        content_type="application/json",
    )


def _float_param(name: str) -> float | None:
    value = request.params.get(name)
    if value is None or value == "":
        return None
    return float(value)


@sub.get("/sentiment/aggregate")
def aggregate_route():
    subject = request.params.get("subject")
    if not subject:
        raise _error(422, "query parameter 'subject' is required")
    try:
        min_confidence = _float_param("min_confidence")
    except ValueError:
        raise _error(422, "min_confidence must be a number")
    try:
        return aggregation_service.aggregate(
            get_repo(),
            subject=subject,
            subject_type=request.params.get("subject_type", "ticker"),
            window=request.params.get("window"),
            source=request.params.get("source"),
            min_confidence=min_confidence,
            time_basis=request.params.get("time_basis", "observed_at"),
        )
    except ValueError as exc:
        raise _error(422, str(exc))


@sub.get("/sentiment/aggregate/timeseries")
def timeseries_route():
    subject = request.params.get("subject")
    if not subject:
        raise _error(422, "query parameter 'subject' is required")
    try:
        min_confidence = _float_param("min_confidence")
    except ValueError:
        raise _error(422, "min_confidence must be a number")
    try:
        return aggregation_service.timeseries(
            get_repo(),
            subject=subject,
            subject_type=request.params.get("subject_type", "ticker"),
            window=request.params.get("window"),
            bucket=request.params.get("bucket"),
            source=request.params.get("source"),
            min_confidence=min_confidence,
            time_basis=request.params.get("time_basis", "observed_at"),
        )
    except ValueError as exc:
        raise _error(422, str(exc))
