import numpy as np

from pocket_option_analyzer.vision.models import (
    CandleCandidate,
    CandleColor,
    CandleFilterDiagnostics,
    CandleSeries,
    CandleType,
    ClassifiedCandle,
    TrendDirection,
)
from pocket_option_analyzer.vision.services import MarketAnalysisPipeline


class FakeCandleAnalysisPipeline:
    last_detection_diagnostics = CandleFilterDiagnostics(
        input_count=23,
        dimension_valid_count=19,
        width_valid_count=12,
        merged_count=12,
        returned_count=12,
        dominant_width=34.0,
    )

    def analyze(self, image):
        return [
            ClassifiedCandle(
                candidate=CandleCandidate(
                    x=10,
                    y=20,
                    width=5,
                    height=30,
                    area=150,
                    color=CandleColor.GREEN,
                ),
                candle_type=CandleType.BULLISH,
            )
        ]


class FakeSeriesBuilder:
    def build(self, candles):
        return CandleSeries(
            candles=tuple(candles),
        )


class FakeTrendDetector:
    def detect(self, series):
        return TrendDirection.BULLISH


def test_analyze_returns_market_analysis() -> None:

    pipeline = MarketAnalysisPipeline(
        candle_analysis_pipeline=FakeCandleAnalysisPipeline(),
        series_builder=FakeSeriesBuilder(),
        trend_detector=FakeTrendDetector(),
    )

    result = pipeline.analyze(
        np.zeros(
            (100, 100, 3),
            dtype=np.uint8,
        )
    )

    assert len(result.series) == 1
    assert result.trend is TrendDirection.BULLISH


def test_market_analysis_preserves_detection_diagnostics() -> None:

    candle_pipeline = FakeCandleAnalysisPipeline()

    pipeline = MarketAnalysisPipeline(
        candle_analysis_pipeline=candle_pipeline,
        series_builder=FakeSeriesBuilder(),
        trend_detector=FakeTrendDetector(),
    )

    result = pipeline.analyze(
        np.zeros(
            (100, 100, 3),
            dtype=np.uint8,
        )
    )

    assert result.detection_diagnostics is (candle_pipeline.last_detection_diagnostics)
