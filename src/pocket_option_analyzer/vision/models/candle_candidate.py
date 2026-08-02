from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .candle_color import CandleColor

if TYPE_CHECKING:
    from pocket_option_analyzer.vision.models.candle_geometry import (
        CandleGeometry,
    )


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
