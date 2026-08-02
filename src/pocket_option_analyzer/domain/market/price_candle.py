from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PriceCandle:
    """
    Representa una vela OHLC.

    Open, high, low y close pueden ser precios reales o valores normalizados
    derivados del gráfico visual.
    """

    open: float

    high: float

    low: float

    close: float

    @property
    def total_range(self) -> float:
        """
        Rango total de la vela.
        """

        return self.high - self.low

    @property
    def body_size(self) -> float:
        """
        Tamaño absoluto del cuerpo de la vela.
        """

        return abs(
            self.close - self.open,
        )

    @property
    def upper_wick_size(self) -> float:
        """
        Tamaño de la mecha superior.
        """

        return self.high - max(
            self.open,
            self.close,
        )

    @property
    def lower_wick_size(self) -> float:
        """
        Tamaño de la mecha inferior.
        """

        return (
            min(
                self.open,
                self.close,
            )
            - self.low
        )

    @property
    def is_bullish(self) -> bool:
        """
        La vela cerró por encima de su apertura.
        """

        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        """
        La vela cerró por debajo de su apertura.
        """

        return self.close < self.open

    @property
    def is_doji(self) -> bool:
        """
        Apertura y cierre prácticamente iguales.
        """

        return self.close == self.open
