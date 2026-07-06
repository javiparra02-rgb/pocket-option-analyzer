import numpy as np

from pocket_option_analyzer.vision.models import (
    CandleCandidate,
    CandleColor,
    CandleType,
    ClassifiedCandle,
)
from pocket_option_analyzer.vision.services import (
    CandleAnalysisPipeline,
)


class FakeDetectionPipeline:

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