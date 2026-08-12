from __future__ import annotations

import numpy as np

from pocket_option_analyzer.vision.models import ChartRegion, MarketAnalysis
from pocket_option_analyzer.vision.services.candle_analysis_pipeline import (
    CandleAnalysisPipeline,
)
from pocket_option_analyzer.vision.services.candle_series_builder import (
    CandleSeriesBuilder,
)
from pocket_option_analyzer.vision.services.current_visual_price_extractor import (
    CurrentVisualPriceExtractor,
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
        current_visual_price_extractor: CurrentVisualPriceExtractor | None = None,
    ) -> None:
        self._candle_analysis_pipeline = candle_analysis_pipeline
        self._series_builder = series_builder
        self._trend_detector = trend_detector
        self._current_visual_price_extractor = current_visual_price_extractor

    def analyze(
        self,
        image: np.ndarray,
        price_observation_image: np.ndarray | None = None,
        chart_region: ChartRegion | None = None,
        price_observation_region: ChartRegion | None = None,
    ) -> MarketAnalysis:
        """
        Analiza una imagen del gráfico y devuelve un análisis de mercado.
        """

        classified_candles = self._candle_analysis_pipeline.analyze(image)

        current_visual_price = None

        if self._current_visual_price_extractor is not None:
            visual_price_image = (
                price_observation_image
                if price_observation_image is not None
                else image
            )
            current_visual_price = (
                self._current_visual_price_extractor.extract(visual_price_image)
            )

        series = self._series_builder.build(classified_candles)

        trend = self._trend_detector.detect(series)

        return MarketAnalysis(
            series=series,
            trend=trend,
            detection_diagnostics=(
                self._candle_analysis_pipeline.last_detection_diagnostics
            ),
            current_visual_price=current_visual_price,
            chart_region=chart_region,
            price_observation_region=price_observation_region,
        )
