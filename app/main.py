"""Bottle application entry point for the quant_sentiment API."""

from __future__ import annotations

import json
import logging
import os
import sys

from bottle import Bottle, response

from app.routes import aggregate, health, sentiment

SERVICE_NAME = "quant-sentiment-api"
log = logging.getLogger(SERVICE_NAME)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stderr,
    force=True,
)


def create_app() -> Bottle:
    """Assemble the Bottle application from its route modules."""
    app = Bottle()
    app.merge(health.sub)
    app.merge(sentiment.sub)
    app.merge(aggregate.sub)

    @app.hook("after_request")
    def _add_cors_headers():
        response.set_header("Access-Control-Allow-Origin", "*")
        response.set_header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
        response.set_header("Access-Control-Allow-Headers", "*")

    def _cors_preflight(**_kwargs):
        response.status = 204
        return ""

    for _path in (
        "/sentiment",
        "/sentiment/health",
        "/sentiment/ready",
        "/sentiment/stats",
        "/sentiment/recent",
        "/sentiment/by-subject/<subject>",
        f"/sentiment/<sentiment_id:re:{sentiment.UUID_RE}>",
        "/sentiment/aggregate",
        "/sentiment/aggregate/timeseries",
    ):
        app.route(_path, method="OPTIONS")(_cors_preflight)

    def _json_error(error):
        response.content_type = "application/json"
        return json.dumps({"detail": _DEFAULT_ERRORS.get(error.status_code, "error")})

    for _code in _DEFAULT_ERRORS:
        app.error(_code)(_json_error)

    return app


_DEFAULT_ERRORS = {
    404: "not found",
    405: "method not allowed",
    500: "internal server error",
}


app = create_app()


if __name__ == "__main__":
    from waitress import serve

    host = os.environ.get("API_LISTEN_ADDRESS", "0.0.0.0")
    port = int(os.environ.get("API_PORT", "8017"))
    log.info("Starting quant_sentiment API on %s:%d ...", host, port)
    serve(app, host=host, port=port, threads=20)
