from __future__ import annotations

from dataclasses import dataclass


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