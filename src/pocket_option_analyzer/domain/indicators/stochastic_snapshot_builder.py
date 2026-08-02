from __future__ import annotations

from pocket_option_analyzer.domain.indicators.stochastic_calculator import (
    StochasticCalculator,
)
from pocket_option_analyzer.domain.indicators.stochastic_snapshot import (
    StochasticSnapshot,
)
from pocket_option_analyzer.domain.market import PriceSeries
from pocket_option_analyzer.domain.strategy import StrategyProfile


class StochasticSnapshotBuilder:
    """
    Construye un StochasticSnapshot usando una serie de precios
    y la configuración de estrategia.
    """

    def __init__(
        self,
        calculator: StochasticCalculator | None = None,
    ) -> None:
        self._calculator = calculator or StochasticCalculator()

    def build(
        self,
        series: PriceSeries,
        profile: StrategyProfile,
    ) -> StochasticSnapshot | None:
        """
        Calcula el estado actual y anterior del Stochastic.

        Si no hay suficientes datos para tener %K y %D actuales
        y anteriores, devuelve None.
        """

        (
            k_values,
            d_values,
            diagnostics,
        ) = self._calculator.calculate_with_diagnostics(
            highs=series.highs,
            lows=series.lows,
            closes=series.closes,
            k_period=profile.stoch_k_period,
            d_period=profile.stoch_d_period,
            smooth_period=profile.stoch_smooth_period,
        )

        if len(k_values) < 2 or len(d_values) < 2:
            return None

        aligned_k_values = self._align_k_values(
            k_values=k_values,
            d_values=d_values,
        )

        return StochasticSnapshot(
            k_previous=aligned_k_values[-2],
            d_previous=d_values[-2],
            k_value=aligned_k_values[-1],
            d_value=d_values[-1],
            diagnostics=diagnostics,
        )

    def _align_k_values(
        self,
        k_values: tuple[float, ...],
        d_values: tuple[float, ...],
    ) -> tuple[float, ...]:
        """
        Alinea los valores de %K con los valores disponibles de %D.

        %D empieza más tarde porque es una media móvil de %K.
        """

        return k_values[
            -len(
                d_values,
            ) :
        ]
