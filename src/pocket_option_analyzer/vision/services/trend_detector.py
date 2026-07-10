from __future__ import annotations

from pocket_option_analyzer.vision.models import (
    CandleSeries,
    CandleType,
    ClassifiedCandle,
    TrendDirection,
)


class TrendDetector:
    """
    Detecta la tendencia visual de una serie de velas.

    Prioridad de decisión:
    1. Momentum direccional reciente.
    2. Movimiento vertical visual.
    3. Proporción general de velas recientes.

    Para evitar ruido, ignora velas:
    - DOJI
    - UNKNOWN
    """

    def __init__(
        self,
        min_candles: int = 5,
        min_directional_candles: int = 3,
        recent_candles: int = 12,
        recent_momentum_candles: int = 3,
        directional_ratio: float = 0.45,
        min_vertical_movement: float = 8.0,
        ignore_latest_candle: bool = True,
    ) -> None:
        self._min_candles = min_candles
        self._min_directional_candles = min_directional_candles
        self._recent_candles = recent_candles
        self._recent_momentum_candles = recent_momentum_candles
        self._directional_ratio = directional_ratio
        self._min_vertical_movement = min_vertical_movement
        self._ignore_latest_candle = ignore_latest_candle

    def detect(
        self,
        series: CandleSeries,
    ) -> TrendDirection:
        """
        Devuelve la tendencia visual dominante.
        """

        candles = tuple(
            series.candles,
        )

        if len(candles) < self._min_candles:
            return TrendDirection.UNKNOWN

        analysis_candles = self._analysis_candles(
            candles=candles,
        )

        recent_candles = tuple(
            analysis_candles[-self._recent_candles :]
        )

        directional_candles = self._directional_candles(
            candles=recent_candles,
        )

        if len(directional_candles) < self._min_directional_candles:
            return TrendDirection.SIDEWAYS

        momentum_direction = self._recent_momentum_direction(
            directional_candles=directional_candles,
        )

        if momentum_direction is not TrendDirection.UNKNOWN:
            return momentum_direction

        bullish_count = self._count_type(
            candles=directional_candles,
            candle_type=CandleType.BULLISH,
        )
        bearish_count = self._count_type(
            candles=directional_candles,
            candle_type=CandleType.BEARISH,
        )

        total_directional = bullish_count + bearish_count

        if total_directional == 0:
            return TrendDirection.SIDEWAYS

        bullish_ratio = bullish_count / total_directional
        bearish_ratio = bearish_count / total_directional

        first_center_y = self._center_y(
            directional_candles[0],
        )
        latest_center_y = self._center_y(
            directional_candles[-1],
        )

        vertical_movement = latest_center_y - first_center_y

        if (
            vertical_movement >= self._min_vertical_movement
            and bearish_ratio >= self._directional_ratio
        ):
            return TrendDirection.BEARISH

        if (
            vertical_movement <= -self._min_vertical_movement
            and bullish_ratio >= self._directional_ratio
        ):
            return TrendDirection.BULLISH

        if bearish_ratio >= 0.7:
            return TrendDirection.BEARISH

        if bullish_ratio >= 0.7:
            return TrendDirection.BULLISH

        return TrendDirection.SIDEWAYS

    def _analysis_candles(
        self,
        candles: tuple[ClassifiedCandle, ...],
    ) -> tuple[ClassifiedCandle, ...]:

        if (
            self._ignore_latest_candle
            and len(candles) > self._min_candles
        ):
            return candles[:-1]

        return candles

    def _recent_momentum_direction(
        self,
        directional_candles: tuple[ClassifiedCandle, ...],
    ) -> TrendDirection:

        recent = directional_candles[
            -self._recent_momentum_candles :
        ]

        if len(recent) < self._recent_momentum_candles:
            return TrendDirection.UNKNOWN

        if all(
            candle.candle_type is CandleType.BEARISH
            for candle in recent
        ):
            return TrendDirection.BEARISH

        if all(
            candle.candle_type is CandleType.BULLISH
            for candle in recent
        ):
            return TrendDirection.BULLISH

        return TrendDirection.UNKNOWN

    def _directional_candles(
        self,
        candles: tuple[ClassifiedCandle, ...],
    ) -> tuple[ClassifiedCandle, ...]:

        return tuple(
            candle
            for candle in candles
            if candle.candle_type
            in {
                CandleType.BULLISH,
                CandleType.BEARISH,
            }
        )

    def _count_type(
        self,
        candles: tuple[ClassifiedCandle, ...],
        candle_type: CandleType,
    ) -> int:

        return sum(
            1
            for candle in candles
            if candle.candle_type is candle_type
        )

    def _center_y(
        self,
        candle: ClassifiedCandle,
    ) -> float:

        return candle.candidate.y + candle.candidate.height / 2