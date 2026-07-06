from pocket_option_analyzer.vision.models import (
    CandleCandidate,
    CandleType,
)
from pocket_option_analyzer.vision.services.candle_classifier import (
    CandleClassifier,
)


def test_classify_returns_unknown():

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