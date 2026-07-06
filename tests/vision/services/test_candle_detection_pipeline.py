import numpy as np

from pocket_option_analyzer.vision.models import CandleCandidate
from pocket_option_analyzer.vision.services import CandleDetectionPipeline


class FakeMaskBuilder:

    def build(self, image):
        return image


class FakeSegmenter:

    def segment(self, mask):
        return [
            CandleCandidate(
                x=10,
                y=10,
                width=5,
                height=20,
                area=100,
            )
        ]


class FakeFilter:

    def filter(self, candles):
        return candles


def test_detect_returns_candidates():

    pipeline = CandleDetectionPipeline(
        mask_builder=FakeMaskBuilder(),
        segmenter=FakeSegmenter(),
        candle_filter=FakeFilter(),
    )

    result = pipeline.detect(
        np.zeros((100, 100), dtype=np.uint8)
    )

    assert len(result) == 1