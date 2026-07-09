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

    La detección considera:
    - velas recientes
    - desplazamiento vertical del precio
    - proporción de velas alcistas/bajistas

    En coordenadas de pantalla:
    - menor y = precio más alto
    - mayor y = precio más bajo
    """

    def __init__(
        self,
        min_candles: int = 5,
        recent_candles: int = 12,
        directional_ratio: float = 0.5,
        min_vertical_movement: float = 8.0,
    ) -> None:
        self._min_candles = min_candles
        self._recent_candles = recent_candles
        self._directional_ratio = directional_ratio
        self._min_vertical_movement = min_vertical_movement

    def detect(
        self,
        series: CandleSeries,
    ) -> TrendDirection:
        """
        Devuelve la tendencia visual dominante.
        """

        if len(series) < self._min_candles:
            return TrendDirection.UNKNOWN

        candles = tuple(
            series.candles[-self._recent_candles :]
        )

        if len(candles) < self._min_candles:
            return TrendDirection.UNKNOWN

        bullish_count = sum(
            1
            for candle in candles
            if candle.candle_type is CandleType.BULLISH
        )
        bearish_count = sum(
            1
            for candle in candles
            if candle.candle_type is CandleType.BEARISH
        )

        total_directional = bullish_count + bearish_count

        if total_directional == 0:
            return TrendDirection.SIDEWAYS

        bullish_ratio = bullish_count / total_directional
        bearish_ratio = bearish_count / total_directional

        first_center_y = self._center_y(
            candles[0],
        )
        latest_center_y = self._center_y(
            candles[-1],
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

    def _center_y(
        self,
        candle: ClassifiedCandle,
    ) -> float:
        """
        Calcula el centro vertical de la vela.

        CandleCandidate no expone center_y directamente, por eso se calcula
        desde y + height / 2.
        """

        return candle.candidate.y + candle.candidate.height / 2