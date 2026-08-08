from __future__ import annotations

from dataclasses import dataclass

from .candle_filter_diagnostics import CandleFilterDiagnostics
from .candle_series import CandleSeries
from .trend_direction import TrendDirection


@dataclass(frozen=True, slots=True)
class MarketAnalysis:
    """
    Resultado de alto nivel del análisis visual del gráfico.

    Incluye opcionalmente el diagnóstico de la detección que originó
    la serie de velas.
    """

    series: CandleSeries

    trend: TrendDirection

    detection_diagnostics: CandleFilterDiagnostics | None = None
