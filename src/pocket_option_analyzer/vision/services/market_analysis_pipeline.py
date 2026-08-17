from __future__ import annotations

from dataclasses import replace

import numpy as np

from pocket_option_analyzer.vision.models import (
    CandleAnalysisResult,
    CandleAnchorExclusionReason,
    CandleDetectionTrace,
    ChartRegion,
    ClassifiedCandle,
    FinalCandleTrace,
    MarketAnalysis,
)
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

        candle_analysis = self._analyze_candles(image)
        classified_candles = (
            list(candle_analysis.candles)
            if candle_analysis is not None
            else self._candle_analysis_pipeline.analyze(image)
        )

        current_visual_price = None
        current_visual_price_detection_trace = None

        if self._current_visual_price_extractor is not None:
            visual_price_image = (
                price_observation_image
                if price_observation_image is not None
                else image
            )
            extract_with_trace = getattr(
                self._current_visual_price_extractor,
                "extract_with_trace",
                None,
            )
            if callable(extract_with_trace):
                visual_price_analysis = extract_with_trace(visual_price_image)
                current_visual_price = visual_price_analysis.extraction
                current_visual_price_detection_trace = visual_price_analysis.trace
            else:
                current_visual_price = self._current_visual_price_extractor.extract(
                    visual_price_image
                )

        series = self._series_builder.build(classified_candles)

        candle_detection_trace = (
            self._finalize_candle_trace(candle_analysis, series.candles)
            if candle_analysis is not None
            else None
        )

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
            candle_detection_trace=candle_detection_trace,
            current_visual_price_detection_trace=(current_visual_price_detection_trace),
        )

    def _analyze_candles(
        self,
        image: np.ndarray,
    ) -> CandleAnalysisResult | None:
        analyze_with_trace = getattr(
            self._candle_analysis_pipeline,
            "analyze_with_trace",
            None,
        )
        if not callable(analyze_with_trace):
            return None
        return analyze_with_trace(image)

    @staticmethod
    def _finalize_candle_trace(
        analysis: CandleAnalysisResult,
        ordered_candles: tuple[ClassifiedCandle, ...],
    ) -> CandleDetectionTrace:
        candidate_ids_by_identity = {
            id(candle.candidate): candidate_id
            for candle, candidate_id in zip(
                analysis.candles,
                analysis.candidate_ids,
                strict=True,
            )
        }
        candidate_traces = {
            candidate.candidate_id: candidate for candidate in analysis.trace.candidates
        }
        latest = ordered_candles[-1] if ordered_candles else None
        final_candles = []
        for ordinal, candle in enumerate(ordered_candles):
            candidate = candle.candidate
            candidate_id = candidate_ids_by_identity[id(candidate)]
            candidate_trace = candidate_traces[candidate_id]
            is_latest = candle is latest
            final_candles.append(
                FinalCandleTrace(
                    candidate_id=candidate_id,
                    source_candidate_ids=(
                        candidate_trace.merged_from or (candidate_id,)
                    ),
                    ordinal=ordinal,
                    x=candidate.x,
                    y=candidate.y,
                    width=candidate.width,
                    height=candidate.height,
                    area=candidate.area,
                    color=candidate.color,
                    candle_type=candle.candle_type,
                    geometry=candidate.geometry,
                    is_latest=is_latest,
                    anchor_exclusion_reason=(
                        CandleAnchorExclusionReason.LATEST
                        if is_latest
                        else CandleAnchorExclusionReason.NOT_EVALUATED
                    ),
                )
            )
        return replace(
            analysis.trace,
            final_candles=tuple(final_candles),
        )
