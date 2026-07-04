"""Derivation of the categorical sentiment label from the numeric score.

The label is never submitted by producers; it is computed here so the whole
platform shares one definition. A score whose absolute value falls within the
configured neutral band derives to ``neutral``.
"""

from __future__ import annotations

from app.config import settings
from app.models.domain import SentimentLabel


def derive_label(score: float, neutral_band: float | None = None) -> SentimentLabel:
    band = settings.neutral_band if neutral_band is None else neutral_band
    if score > band:
        return SentimentLabel.bullish
    if score < -band:
        return SentimentLabel.bearish
    return SentimentLabel.neutral
