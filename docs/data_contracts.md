# Data Contracts

The system of record is a single append-only PostgreSQL table,
`sentiment.sentiment_observations`. Observations are **never updated or
deleted** — corrections are new observations.

## Table: `sentiment.sentiment_observations`

| Column | Type | Notes |
|---|---|---|
| `id` | BIGSERIAL PK | Internal surrogate key (not exposed by the API) |
| `sentiment_id` | UUID, unique | Public identifier (app-generated uuid4) |
| `source` | TEXT | Producer name |
| `idempotency_key` | TEXT | Unique per `source` (dedup) |
| `subject_type` | TEXT | `ticker` / `sector` / `theme` / `market` |
| `subject` | TEXT | As submitted |
| `canonical_subject` | TEXT | Normalized (upper for ticker/market, lower otherwise) |
| `sentiment_label` | TEXT | **Derived** from score: `bullish` / `bearish` / `neutral` |
| `sentiment_score` | DOUBLE PRECISION | Required, range **[-100, 100]** |
| `confidence` | DOUBLE PRECISION | Optional, `[0, 1]` |
| `source_weight` | DOUBLE PRECISION | Optional, `[0, 1]` |
| `horizon` | TEXT | Optional, e.g. `1d`, `5d` |
| `market` | TEXT | Default `stocks` |
| `locale` | TEXT | Default `us` |
| `reason` | TEXT | Optional free text |
| `tags` | JSONB | Array of strings |
| `metadata` | JSONB | Producer payload (max 16 KB) |
| `observed_at` | TIMESTAMPTZ | When measured (defaults to receipt time) |
| `received_at` | TIMESTAMPTZ | Server receipt time |
| `schema_version` | INTEGER | Currently `1` |

Constraints & indexes: `UNIQUE (source, idempotency_key)`; indexes on
`(subject_type, canonical_subject, observed_at)`, `source`, `received_at`,
`sentiment_label`.

## Immutability

* The application exposes no update/delete paths.
* A defense-in-depth trigger (`trg_sentiment_append_only`) raises on any
  `UPDATE`/`DELETE` at the database layer.

## Label derivation

`sentiment_label` is computed from `sentiment_score` using the neutral band
(`QUANT_SENTIMENT_NEUTRAL_BAND`, default `20`):

* `score > band` → `bullish`
* `score < -band` → `bearish`
* otherwise → `neutral`

## Deduplication

Submissions are deduplicated by `(source, idempotency_key)`. A repeated key
returns the originally stored observation with `status = "duplicate"` (HTTP
`200`); the first accept returns `201`.

## Aggregation

Computed at read time (no materialized views in v1). The confidence-weighted
score uses `weight = coalesce(confidence, 1) * coalesce(source_weight, 1)` and
equals `sum(score * weight) / sum(weight)`.
