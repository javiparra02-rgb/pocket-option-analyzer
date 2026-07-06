from __future__ import annotations

from enum import Enum


class CandleColor(str, Enum):
    """
    Color detectado para una vela candidata.
    """

    GREEN = "green"

    RED = "red"

    WHITE = "white"

    UNKNOWN = "unknown"