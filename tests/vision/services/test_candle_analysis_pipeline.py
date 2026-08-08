import numpy as np

from pocket_option_analyzer.vision.models import (
    CandleCandidate,
    CandleColor,
    CandleFilterDiagnostics,
    CandleType,
    ClassifiedCandle,
)
from pocket_option_analyzer.vision.services import (
    CandleAnalysisPipeline,
)


class FakeDetectionPipeline:
    last_filter_diagnostics = CandleFilterDiagnostics(
        input_count=5,
        dimension_valid_count=4,
        width_valid_count=3,
        merged_count=2,
        returned_count=2,
        dominant_width=50.0,
    )

    def detect(self, image):
        return [
            CandleCandidate(
                x=10,
                y=20,
                width=5,
                height=30,
                area=150,
                color=CandleColor.GREEN,
            )
        ]


class FakeClassificationPipeline:
    def classify(self, candles):
        return [
            ClassifiedCandle(
                candidate=candles[0],
                candle_type=CandleType.BULLISH,
            )
        ]


def test_analyze_returns_classified_candles() -> None:

    pipeline = CandleAnalysisPipeline(
        detection_pipeline=FakeDetectionPipeline(),
        classification_pipeline=FakeClassificationPipeline(),
    )

    result = pipeline.analyze(
        np.zeros(
            (100, 100, 3),
            dtype=np.uint8,
        )
    )

    assert len(result) == 1
    assert result[0].candle_type is CandleType.BULLISH


def test_candle_analysis_pipeline_exposes_detection_diagnostics() -> None:

    detection_pipeline = FakeDetectionPipeline()

    pipeline = CandleAnalysisPipeline(
        detection_pipeline=detection_pipeline,
        classification_pipeline=FakeClassificationPipeline(),
    )

    pipeline.analyze(
        np.zeros(
            (100, 100, 3),
            dtype=np.uint8,
        )
    )

    assert pipeline.last_detection_diagnostics is (
        detection_pipeline.last_filter_diagnostics
    )
