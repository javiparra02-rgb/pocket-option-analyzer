from __future__ import annotations

from collections.abc import Iterable

from pocket_option_analyzer.vision.models import (
    CandleSeries,
    ClassifiedCandle,
)


class CandleSeriesBuilder:
    """
    Construye una serie de velas ordenada temporalmente.

    En una imagen de gráfico, el eje X representa el tiempo:
    - izquierda = velas antiguas
    - derecha = velas recientes

    Por eso siempre ordenamos por candidate.x antes de construir la serie.
    """

    def build(
        self,
        candles: Iterable[ClassifiedCandle],
    ) -> CandleSeries:

        ordered_candles = tuple(
            sorted(
                candles,
                key=lambda candle: candle.candidate.x,
            )
        )

        return CandleSeries(
            candles=ordered_candles,
        )
