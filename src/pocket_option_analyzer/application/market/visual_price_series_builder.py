from __future__ import annotations

from pocket_option_analyzer.domain.market import (
    PriceCandle,
    PriceSeries,
)
from pocket_option_analyzer.vision.models import (
    CandleSeries,
    CandleType,
    ClassifiedCandle,
)


class VisualPriceSeriesBuilder:
    """
    Convierte una serie de velas visuales clasificadas en una serie OHLC.

    La conversión usa precios normalizados derivados de coordenadas Y:
    - menor Y en pantalla equivale a mayor precio
    - mayor Y en pantalla equivale a menor precio

    No usa precios reales de Pocket Option.
    No interactúa con la plataforma.
    Solo transforma información visual ya detectada.
    """

    def build(
        self,
        series: CandleSeries,
    ) -> PriceSeries:
        """
        Construye una PriceSeries ordenada de izquierda a derecha.

        Las velas UNKNOWN se omiten porque no tienen dirección confiable.
        """

        candles = tuple(
            candle
            for candle in series.candles
            if candle.candle_type is not CandleType.UNKNOWN
        )

        if not candles:
            return PriceSeries(
                candles=(),
            )

        ordered_candles = tuple(
            sorted(
                candles,
                key=lambda candle: candle.candidate.x,
            )
        )

        chart_bottom = max(
            candle.candidate.y + candle.candidate.height
            for candle in ordered_candles
        )

        return PriceSeries(
            candles=tuple(
                self._to_price_candle(
                    candle=candle,
                    chart_bottom=chart_bottom,
                )
                for candle in ordered_candles
            ),
        )

    def _to_price_candle(
        self,
        candle: ClassifiedCandle,
        chart_bottom: int,
    ) -> PriceCandle:

        top = candle.candidate.y
        bottom = candle.candidate.y + candle.candidate.height

        high = self._to_normalized_price(
            y=top,
            chart_bottom=chart_bottom,
        )
        low = self._to_normalized_price(
            y=bottom,
            chart_bottom=chart_bottom,
        )

        if candle.candle_type is CandleType.BULLISH:
            return PriceCandle(
                open=low,
                high=high,
                low=low,
                close=high,
            )

        if candle.candle_type is CandleType.BEARISH:
            return PriceCandle(
                open=high,
                high=high,
                low=low,
                close=low,
            )

        midpoint = (
            high + low
        ) / 2

        return PriceCandle(
            open=midpoint,
            high=high,
            low=low,
            close=midpoint,
        )

    def _to_normalized_price(
        self,
        y: int,
        chart_bottom: int,
    ) -> float:

        return float(
            chart_bottom - y,
        )