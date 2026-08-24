from __future__ import annotations

from dataclasses import dataclass

from .candle_color import CandleColor
from .candle_geometry import CandleGeometry
from .candle_observability import CandleObservability


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
    geometry: CandleGeometry | None = None
    observability: CandleObservability | None = None

    def __post_init__(self) -> None:
        if self.observability is None:
            return
        if self.geometry is None:
            raise ValueError("observability requiere geometry.")
        if (
            self.observability.body_top_y != self.geometry.body_top_y
            or self.observability.body_bottom_y != self.geometry.body_bottom_y
        ):
            raise ValueError("observability debe coincidir con geometry.")
