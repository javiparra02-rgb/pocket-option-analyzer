from __future__ import annotations

from dataclasses import dataclass

from .price_candle import PriceCandle


@dataclass(frozen=True, slots=True)
class PriceSeries:
    """
    Serie ordenada de velas OHLC.

    El orden esperado es:
    - primera vela: más antigua
    - última vela: más reciente
    """

    candles: tuple[PriceCandle, ...]

    def __len__(self) -> int:
        return len(self.candles)

    def is_empty(self) -> bool:
        return len(self.candles) == 0

    @property
    def latest(self) -> PriceCandle | None:
        """
        Devuelve la vela más reciente.
        """

        if self.is_empty():
            return None

        return self.candles[-1]

    @property
    def closes(self) -> tuple[float, ...]:
        return tuple(
            candle.close
            for candle in self.candles
        )

    @property
    def highs(self) -> tuple[float, ...]:
        return tuple(
            candle.high
            for candle in self.candles
        )

    @property
    def lows(self) -> tuple[float, ...]:
        return tuple(
            candle.low
            for candle in self.candles
        )

    def last(
        self,
        count: int,
    ) -> PriceSeries:
        """
        Devuelve las últimas N velas de la serie.
        """

        if count <= 0:
            return PriceSeries(
                candles=(),
            )

        return PriceSeries(
            candles=self.candles[-count:],
        )