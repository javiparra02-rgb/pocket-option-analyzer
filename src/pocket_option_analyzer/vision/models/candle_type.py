from __future__ import annotations

from enum import Enum


class CandleType(str, Enum):
    """
    Clasificación básica de una vela.
    """

    BULLISH = "bullish"

    BEARISH = "bearish"

    DOJI = "doji"

    UNKNOWN = "unknown"