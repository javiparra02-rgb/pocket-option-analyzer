from pocket_option_analyzer.vision.models import (
    CandleCandidate,
    CandleColor,
    CandleColorProfile,
    CandleType,
)
from pocket_option_analyzer.vision.services import (
    CandleClassificationPipeline,
    CandleClassifier,
)


def test_classify_returns_one_result_per_candidate() -> None:

    pipeline = CandleClassificationPipeline(
        classifier=CandleClassifier(),
    )

    candles = [
        CandleCandidate(
            x=10,
            y=20,
            width=5,
            height=30,
            area=150,
            color=CandleColor.GREEN,
        ),
        CandleCandidate(
            x=20,
            y=20,
            width=5,
            height=30,
            area=150,
            color=CandleColor.RED,
        ),
    ]

    result = pipeline.classify(candles)

    assert len(result) == 2


def test_classify_uses_configured_color_profile() -> None:

    pipeline = CandleClassificationPipeline(
        classifier=CandleClassifier(
            color_profile=CandleColorProfile.white_red(),
        ),
    )

    candles = [
        CandleCandidate(
            x=10,
            y=20,
            width=5,
            height=30,
            area=150,
            color=CandleColor.WHITE,
        ),
        CandleCandidate(
            x=20,
            y=20,
            width=5,
            height=30,
            area=150,
            color=CandleColor.RED,
        ),
    ]

    result = pipeline.classify(candles)

    assert result[0].candle_type is CandleType.BULLISH
    assert result[1].candle_type is CandleType.BEARISH