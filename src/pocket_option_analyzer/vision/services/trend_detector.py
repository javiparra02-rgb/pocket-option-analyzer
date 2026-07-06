from __future__ import annotations

from pocket_option_analyzer.vision.models.candle_series import CandleSeries
from pocket_option_analyzer.vision.models.candle_type import CandleType
from pocket_option_analyzer.vision.models.trend_direction import (
    TrendDirection,
)


class TrendDetector:
    """
    Detecta la dirección dominante de una serie de velas.

    Esta primera versión utiliza la proporción de velas bullish/bearish.
    En futuros sprints se complementará con estructura de mercado.
    """

    def __init__(
        self,
        min_candles: int = 3,
        dominance_threshold: float = 0.6,
    ) -> None:
        self._min_candles = min_candles
        self._dominance_threshold = dominance_threshold

    def detect(
        self,
        series: CandleSeries,
    ) -> TrendDirection:
        """
        Devuelve la tendencia dominante de una serie de velas.
        """

        if len(series) < self._min_candles:
            return TrendDirection.UNKNOWN

        bullish_count = self._count_candles(
            series=series,
            candle_type=CandleType.BULLISH,
        )
        bearish_count = self._count_candles(
            series=series,
            candle_type=CandleType.BEARISH,
        )

        directional_count = bullish_count + bearish_count

        if directional_count < self._min_candles:
            return TrendDirection.UNKNOWN

        bullish_ratio = bullish_count / directional_count
        bearish_ratio = bearish_count / directional_count

        if bullish_ratio >= self._dominance_threshold:
            return TrendDirection.BULLISH

        if bearish_ratio >= self._dominance_threshold:
            return TrendDirection.BEARISH

        return TrendDirection.SIDEWAYS

    def _count_candles(
        self,
        series: CandleSeries,
        candle_type: CandleType,
    ) -> int:

        return sum(
            1
            for candle in series.candles
            if candle.candle_type is candle_type
        )