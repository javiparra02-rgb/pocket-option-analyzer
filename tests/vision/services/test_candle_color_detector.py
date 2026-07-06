import numpy as np

from pocket_option_analyzer.vision.models import (
    CandleCandidate,
    CandleColor,
)
from pocket_option_analyzer.vision.services.candle_color_detector import (
    CandleColorDetector,
)


def test_detects_white_candle() -> None:

    image = np.zeros(
        (40, 40, 3),
        dtype=np.uint8,
    )

    image[10:30, 10:20] = (255, 255, 255)

    candle = CandleCandidate(
        x=10,
        y=10,
        width=10,
        height=20,
        area=200,
    )

    detector = CandleColorDetector()

    result = detector.detect(
        image=image,
        candle=candle,
    )

    assert result is CandleColor.WHITE


def test_detects_red_candle() -> None:

    image = np.zeros(
        (40, 40, 3),
        dtype=np.uint8,
    )

    image[10:30, 10:20] = (0, 0, 255)

    candle = CandleCandidate(
        x=10,
        y=10,
        width=10,
        height=20,
        area=200,
    )

    detector = CandleColorDetector()

    result = detector.detect(
        image=image,
        candle=candle,
    )

    assert result is CandleColor.RED


def test_detects_green_candle() -> None:

    image = np.zeros(
        (40, 40, 3),
        dtype=np.uint8,
    )

    image[10:30, 10:20] = (0, 255, 0)

    candle = CandleCandidate(
        x=10,
        y=10,
        width=10,
        height=20,
        area=200,
    )

    detector = CandleColorDetector()

    result = detector.detect(
        image=image,
        candle=candle,
    )

    assert result is CandleColor.GREEN


def test_returns_unknown_when_no_valid_color_is_detected() -> None:

    image = np.zeros(
        (40, 40, 3),
        dtype=np.uint8,
    )

    candle = CandleCandidate(
        x=10,
        y=10,
        width=10,
        height=20,
        area=200,
    )

    detector = CandleColorDetector()

    result = detector.detect(
        image=image,
        candle=candle,
    )

    assert result is CandleColor.UNKNOWN    