from __future__ import annotations

from pocket_option_analyzer.vision.models import (
    CandleCandidate,
    ClassifiedCandle,
)
from pocket_option_analyzer.vision.services.candle_classifier import (
    CandleClassifier,
)


class CandleClassificationPipeline:
    """
    Pipeline encargado de clasificar una colección de velas candidatas.
    """

    def __init__(
        self,
        classifier: CandleClassifier,
    ) -> None:
        self._classifier = classifier

    def classify(
        self,
        candles: list[CandleCandidate],
    ) -> list[ClassifiedCandle]:
        """
        Clasifica una lista de velas candidatas.
        """

        return [self._classifier.classify(candle) for candle in candles]
