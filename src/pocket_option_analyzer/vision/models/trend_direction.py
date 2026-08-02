from __future__ import annotations

from enum import Enum


class TrendDirection(str, Enum):
    """
    Dirección general detectada en una serie de velas.
    """

    BULLISH = "bullish"

    BEARISH = "bearish"

    SIDEWAYS = "sideways"

    UNKNOWN = "unknown"
