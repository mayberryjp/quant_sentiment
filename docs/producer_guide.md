# Sentiment Producer Integration Guide

## Overview

Producers submit market-sentiment observations to `POST /sentiment`. Each
observation says: "source X believes subject Y has sentiment score Z at time T."
The service derives a categorical label, stores the observation immutably, and
makes it available for retrieval and aggregation.

## Endpoint

```
POST /sentiment
Content-Type: application/json
```

## Fields

| Field | Type | Constraints | Description |
|---|---|---|---|
| `source` | string | 1–128, required | Producer name (e.g. `news-nlp-v1`) |
| `idempotency_key` | string | 1–512, required | Unique per submission for the source |
| `subject_type` | string | `ticker`\|`sector`\|`theme`\|`market` (default `ticker`) | Kind of subject |
| `subject` | string | 1–64, required | e.g. `AAPL`, `technology` |
| `sentiment_score` | number | **-100 … 100**, required | Signed intensity |
| `confidence` | number | 0–1, optional | Confidence in this observation |
| `source_weight` | number | 0–1, optional | Producer reliability weight |
| `horizon` | string | ≤ 32, optional | e.g. `1d`, `5d` |
| `market` | string | ≤ 32, default `stocks` | |
| `locale` | string | ≤ 8, default `us` | |
| `reason` | string | ≤ 2000, optional | Rationale |
| `observed_at` | datetime | optional | ISO-8601; defaults to receipt time |
| `tags` | string[] | ≤ 20 items | |
| `metadata` | object | ≤ 16 KB | Producer payload |

> `sentiment_label` is **not** submitted — it is derived from `sentiment_score`.

## Example

```bash
curl -X POST http://localhost:8017/sentiment \
  -H "Content-Type: application/json" \
  -d '{
        "source": "news-nlp-v1",
        "idempotency_key": "news-nlp-v1:2026-07-04:AAPL",
        "subject_type": "ticker",
        "subject": "AAPL",
        "sentiment_score": 62.5,
        "confidence": 0.8,
        "reason": "Strong earnings beat with raised guidance",
        "tags": ["earnings"],
        "metadata": {"model": "nlp-v1"}
      }'
```

Response (`201 Created`):

```json
{
  "status": "accepted",
  "sentiment_id": "b6b0...-...",
  "sentiment_label": "bullish",
  "subject_type": "ticker",
  "canonical_subject": "AAPL"
}
```

Re-sending the same `idempotency_key` returns `200 OK` with
`"status": "duplicate"` and the original `sentiment_id`.

## Idempotency guidance

Use a deterministic key such as `{source}:{date}:{subject}` so retries never
create duplicate observations.
