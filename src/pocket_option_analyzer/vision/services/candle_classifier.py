from __future__ import annotations

from pocket_option_analyzer.vision.models import (
    CandleCandidate,
    CandleColorProfile,
    CandleType,
    ClassifiedCandle,
)


class CandleClassifier:
    """
    Clasificador básico de velas según un perfil de color configurable.
    """

    def __init__(
        self,
        color_profile: CandleColorProfile | None = None,
    ) -> None:
        self._color_profile = color_profile or CandleColorProfile.green_red()

    def classify(
        self,
        candle: CandleCandidate,
    ) -> ClassifiedCandle:

        if candle.color is self._color_profile.bullish:
            candle_type = CandleType.BULLISH

        elif candle.color is self._color_profile.bearish:
            candle_type = CandleType.BEARISH

        else:
            candle_type = CandleType.UNKNOWN

        return ClassifiedCandle(
            candidate=candle,
            candle_type=candle_type,
        )
