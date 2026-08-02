from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EmaSnapshot:
    """
    Estado actual de las medias móviles exponenciales usadas por la estrategia.
    """

    fast_value: float

    slow_value: float

    separation_candles: int

    @property
    def is_bullish_alignment(self) -> bool:
        """
        EMA rápida por encima de EMA lenta.
        """

        return self.fast_value > self.slow_value

    @property
    def is_bearish_alignment(self) -> bool:
        """
        EMA rápida por debajo de EMA lenta.
        """

        return self.fast_value < self.slow_value
