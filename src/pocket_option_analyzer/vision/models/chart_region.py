from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ChartRegion:
    """
    Representa la región del gráfico dentro de una imagen.
    """

    x: int
    y: int
    width: int
    height: int