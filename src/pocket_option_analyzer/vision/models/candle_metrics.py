from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CandleMetrics:
    """
    Contiene las métricas geométricas calculadas para una vela.
    """

    x: int
    y: int

    width: int
    height: int

    area: int

    center_x: float
    center_y: float

    aspect_ratio: float