"""Application settings for quant_sentiment.

All tunable knobs are loaded from environment variables using the
``QUANT_SENTIMENT_`` prefix. ``DATABASE_URL`` is read directly (unprefixed) in
``app.db`` to stay consistent with the sibling ``quant_signals`` service.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- Label derivation ------------------------------------------------
    # A score whose absolute value is <= neutral_band derives to "neutral".
    neutral_band: float = 20.0

    # --- Score bounds ----------------------------------------------------
    score_min: float = -100.0
    score_max: float = 100.0

    # --- Validation limits ----------------------------------------------
    max_source_length: int = 128
    max_idempotency_key_length: int = 512
    max_subject_length: int = 64
    max_reason_length: int = 2000
    max_tags: int = 20
    max_metadata_bytes: int = 16_384

    # --- Pagination ------------------------------------------------------
    default_page_size: int = 25
    max_page_size: int = 100

    # --- Aggregation -----------------------------------------------------
    default_window: str = "1d"
    max_window: str = "90d"

    model_config = SettingsConfigDict(env_prefix="QUANT_SENTIMENT_", extra="ignore")


settings = Settings()
