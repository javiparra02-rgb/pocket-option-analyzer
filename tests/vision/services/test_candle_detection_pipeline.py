import cv2
import numpy as np

from pocket_option_analyzer.vision.models import (
    CandleCandidate,
    CandleColor,
    CandleGeometry,
)
from pocket_option_analyzer.vision.services import (
    CandleDetectionPipeline,
    CandleFilter,
    CandleSegmenter,
    PocketOptionCandleMaskBuilder,
)


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


class FakeColorDetector:
    def detect(self, image, candle):
        return CandleColor.WHITE


class FakeGeometryExtractor:
    def __init__(
        self,
        geometry: CandleGeometry,
    ) -> None:
        self.geometry = geometry
        self.received_mask = None
        self.received_candidate = None

    def extract(
        self,
        mask,
        candidate,
    ) -> CandleGeometry:
        self.received_mask = mask
        self.received_candidate = candidate

        return self.geometry


def test_detect_returns_candidates() -> None:

    pipeline = CandleDetectionPipeline(
        mask_builder=FakeMaskBuilder(),
        segmenter=FakeSegmenter(),
        candle_filter=FakeFilter(),
    )

    result = pipeline.detect(np.zeros((100, 100), dtype=np.uint8))

    assert len(result) == 1


def test_detect_assigns_color_when_color_detector_is_configured() -> None:

    pipeline = CandleDetectionPipeline(
        mask_builder=FakeMaskBuilder(),
        segmenter=FakeSegmenter(),
        candle_filter=FakeFilter(),
        color_detector=FakeColorDetector(),
    )

    result = pipeline.detect(np.zeros((100, 100, 3), dtype=np.uint8))

    assert len(result) == 1
    assert result[0].color is CandleColor.WHITE


def test_detection_pipeline_preserves_eighteen_mixed_size_candles() -> None:

    image = np.zeros(
        (
            500,
            1200,
            3,
        ),
        dtype=np.uint8,
    )
    image[:] = (
        25,
        27,
        40,
    )

    body_heights = (
        70,
        3,
        25,
        50,
        8,
        90,
        4,
        35,
        65,
        12,
        100,
        6,
        45,
        20,
        80,
        5,
        55,
        2,
    )

    for index, body_height in enumerate(
        body_heights,
    ):
        # La primera vela representa una vela parcialmente recortada
        # por el borde izquierdo del ROI.
        x = 0 if index == 0 else 20 + index * 55
        body_width = 24 if index == 0 else 36
        top = 160 + (index % 5 - 2) * 20

        color = (
            (
                0,
                0,
                255,
            )
            if index % 2 == 0
            else (
                255,
                255,
                255,
            )
        )

        center_x = x + body_width // 2

        cv2.line(
            image,
            (
                center_x,
                top - 15,
            ),
            (
                center_x,
                top + body_height + 15,
            ),
            color,
            thickness=1,
        )
        cv2.rectangle(
            image,
            (
                x,
                top,
            ),
            (
                x + body_width - 1,
                top + body_height - 1,
            ),
            color,
            thickness=-1,
        )

    for index in range(8):
        cv2.rectangle(
            image,
            (
                40 + index * 15,
                40,
            ),
            (
                45 + index * 15,
                54,
            ),
            (
                255,
                255,
                255,
            ),
            thickness=-1,
        )

    pipeline = CandleDetectionPipeline(
        mask_builder=PocketOptionCandleMaskBuilder(),
        segmenter=CandleSegmenter(),
        candle_filter=CandleFilter(),
    )

    result = pipeline.detect(
        image=image,
    )

    assert len(result) == 18
    assert result[0].width == 24
    assert all(candidate.width == 36 for candidate in result[1:])


def test_detect_assigns_candle_geometry_when_extractor_is_configured() -> None:

    geometry = CandleGeometry(
        high_y=10,
        body_top_y=15,
        body_bottom_y=25,
        low_y=29,
    )
    geometry_extractor = FakeGeometryExtractor(
        geometry=geometry,
    )

    image = np.zeros(
        (
            100,
            100,
        ),
        dtype=np.uint8,
    )

    pipeline = CandleDetectionPipeline(
        mask_builder=FakeMaskBuilder(),
        segmenter=FakeSegmenter(),
        candle_filter=FakeFilter(),
        geometry_extractor=geometry_extractor,
    )

    result = pipeline.detect(
        image=image,
    )

    assert len(result) == 1
    assert result[0].geometry is geometry
    assert geometry_extractor.received_mask is image
    assert geometry_extractor.received_candidate.x == 10
