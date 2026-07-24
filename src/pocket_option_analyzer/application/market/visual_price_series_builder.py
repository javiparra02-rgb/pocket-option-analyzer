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
    Convierte velas visuales clasificadas en una serie OHLC normalizada.

    Sistema de coordenadas:

    - una coordenada Y menor representa un precio mayor;
    - una coordenada Y mayor representa un precio menor.

    Cuando el candidato contiene CandleGeometry:

    - high y low provienen de los extremos de las mechas;
    - open y close provienen de los bordes del cuerpo.

    Si la geometría no está disponible, se conserva una conversión
    compatible con el comportamiento anterior.
    """

    def build(
        self,
        series: CandleSeries,
    ) -> PriceSeries:
        """
        Construye una PriceSeries ordenada de izquierda a derecha.

        Las velas UNKNOWN se omiten porque no tienen una dirección
        visual suficientemente confiable.
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
            self._resolve_low_y(
                candle=candle,
            )
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
        """
        Convierte una vela clasificada en OHLC normalizado.
        """

        geometry = candle.candidate.geometry

        if geometry is None:
            return self._to_legacy_price_candle(
                candle=candle,
                chart_bottom=chart_bottom,
            )

        high = self._to_normalized_price(
            y=geometry.high_y,
            chart_bottom=chart_bottom,
        )
        low = self._to_normalized_price(
            y=geometry.low_y,
            chart_bottom=chart_bottom,
        )
        body_top = self._to_normalized_price(
            y=geometry.body_top_y,
            chart_bottom=chart_bottom,
        )
        body_bottom = self._to_normalized_price(
            y=geometry.body_bottom_y,
            chart_bottom=chart_bottom,
        )

        if candle.candle_type is CandleType.BULLISH:
            return PriceCandle(
                open=body_bottom,
                high=high,
                low=low,
                close=body_top,
            )

        if candle.candle_type is CandleType.BEARISH:
            return PriceCandle(
                open=body_top,
                high=high,
                low=low,
                close=body_bottom,
            )

        midpoint = (
            body_top
            + body_bottom
        ) / 2.0

        return PriceCandle(
            open=midpoint,
            high=high,
            low=low,
            close=midpoint,
        )

    def _to_legacy_price_candle(
        self,
        candle: ClassifiedCandle,
        chart_bottom: int,
    ) -> PriceCandle:
        """
        Conversión defensiva para candidatos sin CandleGeometry.

        Conserva el comportamiento anterior para no perder por completo
        una vela cuando la extracción geométrica no está disponible.
        """

        top = candle.candidate.y
        bottom = (
            candle.candidate.y
            + candle.candidate.height
        )

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
            high
            + low
        ) / 2.0

        return PriceCandle(
            open=midpoint,
            high=high,
            low=low,
            close=midpoint,
        )

    @staticmethod
    def _resolve_low_y(
        candle: ClassifiedCandle,
    ) -> int:
        """
        Obtiene el extremo inferior visual usado como base común.
        """

        geometry = candle.candidate.geometry

        if geometry is not None:
            return geometry.low_y

        return (
            candle.candidate.y
            + candle.candidate.height
        )

    @staticmethod
    def _to_normalized_price(
        y: int,
        chart_bottom: int,
    ) -> float:
        return float(
            chart_bottom - y,
        )