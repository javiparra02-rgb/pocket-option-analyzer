from __future__ import annotations

from pocket_option_analyzer.vision.models import (
    CandleCandidate,
    CandleColor,
    CandleType,
    ClassifiedCandle,
)


class CandleClassifier:
    """
    Clasificador básico de velas según su color detectado.
    """

    def classify(
        self,
        candle: CandleCandidate,
    ) -> ClassifiedCandle:

        if candle.color is CandleColor.GREEN:
            candle_type = CandleType.BULLISH

        elif candle.color is CandleColor.RED:
            candle_type = CandleType.BEARISH

        else:
            candle_type = CandleType.UNKNOWN

        return ClassifiedCandle(
            candidate=candle,
            candle_type=candle_type,
        )