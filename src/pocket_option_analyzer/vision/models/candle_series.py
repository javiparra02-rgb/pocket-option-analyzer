from __future__ import annotations

from dataclasses import dataclass

from .classified_candle import ClassifiedCandle


@dataclass(frozen=True, slots=True)
class CandleSeries:
    """
    Representa una serie ordenada de velas clasificadas.
    """

    candles: tuple[ClassifiedCandle, ...]

    def __len__(self) -> int:
        return len(self.candles)

    def is_empty(self) -> bool:
        return len(self.candles) == 0

    @property
    def first(self) -> ClassifiedCandle | None:
        if self.is_empty():
            return None

        return self.candles[0]

    @property
    def latest(self) -> ClassifiedCandle | None:
        if self.is_empty():
            return None

        return self.candles[-1]