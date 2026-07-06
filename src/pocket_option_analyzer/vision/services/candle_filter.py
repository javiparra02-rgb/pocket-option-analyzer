from __future__ import annotations

from pocket_option_analyzer.vision.models import (
    CandleCandidate,
)


class CandleFilter:
    """
    Elimina candidatos que claramente no corresponden a velas.
    """

    def filter(
        self,
        candles: list[CandleCandidate],
    ) -> list[CandleCandidate]:

        result: list[CandleCandidate] = []

        for candle in candles:

            if candle.width < 2:
                continue

            if candle.height < 5:
                continue

            if candle.area < 20:
                continue

            result.append(candle)

        return result