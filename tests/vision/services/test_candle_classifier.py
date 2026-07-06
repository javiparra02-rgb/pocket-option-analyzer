from pocket_option_analyzer.vision.models import (
    CandleCandidate,
    CandleColor,
    CandleColorProfile,
    CandleType,
)
from pocket_option_analyzer.vision.services.candle_classifier import (
    CandleClassifier,
)


def test_classify_returns_unknown_for_unknown_color() -> None:

    classifier = CandleClassifier()

    candle = CandleCandidate(
        x=10,
        y=20,
        width=5,
        height=30,
        area=150,
    )

    result = classifier.classify(candle)

    assert result.candle_type is CandleType.UNKNOWN


def test_classify_returns_bullish_for_green_candle() -> None:

    classifier = CandleClassifier()

    candle = CandleCandidate(
        x=10,
        y=20,
        width=5,
        height=30,
        area=150,
        color=CandleColor.GREEN,
    )

    result = classifier.classify(candle)

    assert result.candle_type is CandleType.BULLISH


def test_classify_returns_bearish_for_red_candle() -> None:

    classifier = CandleClassifier()

    candle = CandleCandidate(
        x=10,
        y=20,
        width=5,
        height=30,
        area=150,
        color=CandleColor.RED,
    )

    result = classifier.classify(candle)

    assert result.candle_type is CandleType.BEARISH


def test_classify_returns_bullish_for_white_candle_with_white_red_profile() -> None:

    classifier = CandleClassifier(
        color_profile=CandleColorProfile.white_red(),
    )

    candle = CandleCandidate(
        x=10,
        y=20,
        width=5,
        height=30,
        area=150,
        color=CandleColor.WHITE,
    )

    result = classifier.classify(candle)

    assert result.candle_type is CandleType.BULLISH