from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RsiSnapshot:
    """
    Estado actual del RSI usado por la estrategia.
    """

    value: float

    def is_above(
        self,
        threshold: float,
    ) -> bool:
        return self.value > threshold

    def is_below(
        self,
        threshold: float,
    ) -> bool:
        return self.value < threshold

    def is_between(
        self,
        minimum: float,
        maximum: float,
    ) -> bool:
        return minimum <= self.value <= maximum