from __future__ import annotations

from dataclasses import dataclass

from .candle_series import CandleSeries
from .trend_direction import TrendDirection


@dataclass(frozen=True, slots=True)
class MarketAnalysis:
    """
    Resultado de alto nivel del análisis visual del gráfico.
    """

    series: CandleSeries

    trend: TrendDirection
