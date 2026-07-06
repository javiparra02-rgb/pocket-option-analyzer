from __future__ import annotations

from dataclasses import dataclass

from .candle_color import CandleColor


@dataclass(frozen=True, slots=True)
class CandleCandidate:
    """
    Representa un objeto candidato a ser una vela.
    """

    x: int
    y: int

    width: int
    height: int

    area: int

    color: CandleColor = CandleColor.UNKNOWN