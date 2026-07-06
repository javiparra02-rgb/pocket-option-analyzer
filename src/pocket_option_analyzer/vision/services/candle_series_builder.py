from __future__ import annotations

from pocket_option_analyzer.vision.models import (
    CandleSeries,
    ClassifiedCandle,
)


class CandleSeriesBuilder:
    """
    Construye una serie de velas ordenada de izquierda a derecha.

    En una imagen de gráfico, el eje X representa el tiempo:
    - menor X = vela más antigua
    - mayor X = vela más reciente
    """

    def build(
        self,
        candles: list[ClassifiedCandle],
    ) -> CandleSeries:

        ordered_candles = sorted(
            candles,
            key=lambda candle: candle.candidate.x,
        )

        return CandleSeries(
            candles=tuple(ordered_candles),
        )