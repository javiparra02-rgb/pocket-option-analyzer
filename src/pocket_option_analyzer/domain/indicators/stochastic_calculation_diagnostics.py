from __future__ import annotations

from dataclasses import dataclass


@dataclass(
    frozen=True,
    slots=True,
)
class StochasticCalculationDiagnostics:
    """
    Explica los valores usados en el último cálculo del Stochastic.

    Los precios pueden representar precios reales o unidades visuales
    normalizadas derivadas del gráfico.
    """

    source_candle_count: int
    k_period: int
    highest_high: float
    lowest_low: float
    latest_close: float
    latest_raw_k: float
    latest_smoothed_k: float
    latest_d: float

    def __post_init__(
        self,
    ) -> None:
        if self.source_candle_count < 1:
            raise ValueError(
                "source_candle_count debe ser mayor o igual a 1."
            )

        if self.k_period < 1:
            raise ValueError(
                "k_period debe ser mayor o igual a 1."
            )

        if self.highest_high < self.lowest_low:
            raise ValueError(
                "highest_high no puede ser menor que lowest_low."
            )

    @property
    def price_range(self) -> float:
        """
        Rango máximo-mínimo de la última ventana de %K.
        """

        return (
            self.highest_high
            - self.lowest_low
        )