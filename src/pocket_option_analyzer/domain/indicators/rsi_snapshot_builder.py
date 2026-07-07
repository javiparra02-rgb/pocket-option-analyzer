from __future__ import annotations

from pocket_option_analyzer.domain.indicators.rsi_calculator import (
    RsiCalculator,
)
from pocket_option_analyzer.domain.indicators.rsi_snapshot import (
    RsiSnapshot,
)
from pocket_option_analyzer.domain.market import PriceSeries
from pocket_option_analyzer.domain.strategy import StrategyProfile


class RsiSnapshotBuilder:
    """
    Construye un RsiSnapshot usando una serie de precios
    y la configuración de estrategia.
    """

    def __init__(
        self,
        calculator: RsiCalculator | None = None,
    ) -> None:
        self._calculator = calculator or RsiCalculator()

    def build(
        self,
        series: PriceSeries,
        profile: StrategyProfile,
    ) -> RsiSnapshot | None:
        """
        Calcula el RSI actual.

        Si no hay suficientes datos para calcular RSI,
        devuelve None.
        """

        values = self._calculator.calculate(
            values=series.closes,
            period=profile.rsi_period,
        )

        if not values:
            return None

        return RsiSnapshot(
            value=values[-1],
        )