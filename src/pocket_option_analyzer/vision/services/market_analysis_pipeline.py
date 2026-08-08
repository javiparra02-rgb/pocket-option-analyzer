from __future__ import annotations

import numpy as np

from pocket_option_analyzer.vision.models import MarketAnalysis
from pocket_option_analyzer.vision.services.candle_analysis_pipeline import (
    CandleAnalysisPipeline,
)
from pocket_option_analyzer.vision.services.candle_series_builder import (
    CandleSeriesBuilder,
)
from pocket_option_analyzer.vision.services.trend_detector import (
    TrendDetector,
)


class MarketAnalysisPipeline:
    """
    Pipeline de alto nivel para analizar el estado visual del mercado.
    """

    def __init__(
        self,
        candle_analysis_pipeline: CandleAnalysisPipeline,
        series_builder: CandleSeriesBuilder,
        trend_detector: TrendDetector,
    ) -> None:
        self._candle_analysis_pipeline = candle_analysis_pipeline
        self._series_builder = series_builder
        self._trend_detector = trend_detector

    def analyze(
        self,
        image: np.ndarray,
    ) -> MarketAnalysis:
        """
        Analiza una imagen del gráfico y devuelve un análisis de mercado.
        """

        classified_candles = self._candle_analysis_pipeline.analyze(image)

        series = self._series_builder.build(classified_candles)

        trend = self._trend_detector.detect(series)

        return MarketAnalysis(
            series=series,
            trend=trend,
            detection_diagnostics=(
                self._candle_analysis_pipeline.last_detection_diagnostics
            ),
        )
