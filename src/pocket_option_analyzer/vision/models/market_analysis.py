from __future__ import annotations

from dataclasses import dataclass

from .candle_filter_diagnostics import CandleFilterDiagnostics
from .candle_series import CandleSeries
from .chart_region import ChartRegion
from .current_visual_price_extraction import CurrentVisualPriceExtraction
from .trend_direction import TrendDirection


@dataclass(frozen=True, slots=True)
class MarketAnalysis:
    """
    Resultado de alto nivel del análisis visual del gráfico.

    Incluye opcionalmente:

    - el diagnóstico de la detección que originó la serie de velas;
    - la extracción diagnóstica independiente del precio visual actual.
    """

    series: CandleSeries

    trend: TrendDirection

    detection_diagnostics: CandleFilterDiagnostics | None = None

    current_visual_price: CurrentVisualPriceExtraction | None = None

    chart_region: ChartRegion | None = None

    price_observation_region: ChartRegion | None = None
