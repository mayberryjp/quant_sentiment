# Operational Runbook

## Health / Readiness

```bash
curl http://localhost:8017/sentiment/health
# {"status": "ok"}   (liveness; no DB dependency)

curl http://localhost:8017/sentiment/ready
# {"status": "ready", "database": "ok"}   (503 if the database is unreachable)
```

## Stats

```bash
curl http://localhost:8017/sentiment/stats
# total_observations, distinct_subjects, distinct_sources,
# label_distribution, last_received_at
```

## Reading observations

```bash
# Recent (filters + pagination)
curl "http://localhost:8017/sentiment/recent?subject=AAPL&sentiment_label=bullish&page=1&page_size=25"

# By id
curl http://localhost:8017/sentiment/<sentiment_id>

# All for a subject
curl http://localhost:8017/sentiment/by-subject/AAPL
```

## Aggregation

```bash
# Single-window aggregate
curl "http://localhost:8017/sentiment/aggregate?subject=AAPL&window=1d&time_basis=observed_at"

# Time series (bucketed)
curl "http://localhost:8017/sentiment/aggregate/timeseries?subject=AAPL&window=1d&bucket=1h"
```

## Running locally (Docker)

```bash
docker compose up --build
# API on :8017, PostgreSQL on :5432. Migrations run on container start.
```

## Running migrations manually

```bash
export DATABASE_URL=postgresql+psycopg://sentiment:sentiment@localhost:5432/sentiment
alembic upgrade head
```

## Running tests

```bash
pip install -e ".[dev]"
pytest -v          # runs against in-memory SQLite; no Docker/Postgres required
```

## Troubleshooting

- `readiness = not_ready` / `database: unavailable` → PostgreSQL is unreachable;
  check `DATABASE_URL` and that the DB container is healthy.
- Intake `422` → payload failed validation (score out of `[-100, 100]`, missing
  `source`/`idempotency_key`/`sentiment_score`, too many tags, oversized
  metadata, or malformed JSON). The response `detail` explains which.
- Duplicate observations are expected: a repeated `(source, idempotency_key)`
  returns `200` with `status = duplicate`; nothing new is written.

## Known limitations (v1)

- Aggregation is computed at read time; no materialized views yet.
- Time-series bucketing is performed in the service layer for backend
  portability.
- No authentication layer (add per platform conventions).
