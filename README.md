# quant_sentiment

Market sentiment aggregation API for the quant/algo trading platform.

Producers submit sentiment observations about market subjects (tickers, sectors,
themes, or the whole market). `quant_sentiment` validates, deduplicates, and
stores every observation **immutably** in PostgreSQL, then exposes read and
aggregation endpoints for downstream signal-processing services. It is an
aggregator only — it does not generate trading signals.

## Quick Start

```bash
# Run the full stack (API on :8017, PostgreSQL on :5432). Migrations run on start.
docker compose up --build

# Run the test suite (in-memory SQLite; no Docker/Postgres needed)
pip install -e ".[dev]"
pytest -v
```

## Architecture

Multiple producers submit observations via `POST /sentiment`. Each observation
is validated, its label derived from the numeric score, its subject canonicalized
(and optionally resolved against a symbol master), then persisted append-only in
PostgreSQL. Deduplication is by `(source, idempotency_key)`. Reads and read-time
SQL aggregates are served from the same store.

PostgreSQL is the sole system of record — sentiment is never updated or deleted.

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/sentiment/health` | Liveness (no DB dependency) |
| GET | `/sentiment/ready` | Readiness (DB reachability) |
| GET | `/sentiment/stats` | Counters computed from the store |
| POST | `/sentiment` | Submit an observation |
| GET | `/sentiment/recent` | Recent observations (filters, pagination) |
| GET | `/sentiment/{sentiment_id}` | Observation detail |
| GET | `/sentiment/by-subject/{subject}` | All observations for a subject |
| GET | `/sentiment/aggregate` | Aggregated sentiment for a subject/window |
| GET | `/sentiment/aggregate/timeseries` | Bucketed aggregates over time |

## Documentation

- [Data Contracts](docs/data_contracts.md) — schema, immutability, dedup, label derivation
- [Producer Guide](docs/producer_guide.md) — integration contract and examples
- [Runbook](docs/runbook.md) — operational commands and troubleshooting

## Configuration

- `DATABASE_URL` — PostgreSQL DSN (required in production).
- `API_LISTEN_ADDRESS` (default `0.0.0.0`), `API_PORT` (default `8017`).
- `QUANT_SENTIMENT_*` — tuning knobs (neutral band, page sizes, aggregation
  window limits). See [.env.example](.env.example).
