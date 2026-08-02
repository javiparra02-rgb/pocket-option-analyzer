from __future__ import annotations

from collections.abc import Sequence

from pocket_option_analyzer.domain.indicators.ema_calculator import (
    EmaCalculator,
)
from pocket_option_analyzer.domain.indicators.ema_snapshot import (
    EmaSnapshot,
)
from pocket_option_analyzer.domain.market import PriceSeries
from pocket_option_analyzer.domain.strategy import StrategyProfile


class EmaSnapshotBuilder:
    """
    Construye un EmaSnapshot usando una serie de precios
    y la configuración de estrategia.
    """

    def __init__(
        self,
        calculator: EmaCalculator | None = None,
    ) -> None:
        self._calculator = calculator or EmaCalculator()

    def build(
        self,
        series: PriceSeries,
        profile: StrategyProfile,
    ) -> EmaSnapshot | None:
        """
        Calcula EMA rápida/lenta y su separación reciente.

        Si no hay suficientes datos para calcular ambas EMAs,
        devuelve None.
        """

        closes = series.closes

        fast_values = self._calculator.calculate(
            values=closes,
            period=profile.ema_fast_period,
        )

        slow_values = self._calculator.calculate(
            values=closes,
            period=profile.ema_slow_period,
        )

        if not fast_values or not slow_values:
            return None

        aligned_fast_values = self._align_fast_values(
            fast_values=fast_values,
            slow_values=slow_values,
        )

        separation_candles = self._calculate_separation_candles(
            fast_values=aligned_fast_values,
            slow_values=slow_values,
        )

        return EmaSnapshot(
            fast_value=fast_values[-1],
            slow_value=slow_values[-1],
            separation_candles=separation_candles,
        )

    def _align_fast_values(
        self,
        fast_values: Sequence[float],
        slow_values: Sequence[float],
    ) -> tuple[float, ...]:
        """
        Alinea la EMA rápida con la EMA lenta.

        Como la EMA lenta necesita más datos para empezar,
        se comparan únicamente los valores coincidentes más recientes.
        """

        return tuple(
            fast_values[-len(slow_values) :],
        )

    def _calculate_separation_candles(
        self,
        fast_values: Sequence[float],
        slow_values: Sequence[float],
    ) -> int:
        """
        Cuenta cuántas velas recientes mantienen la misma separación:
        - EMA rápida encima de EMA lenta
        - o EMA rápida debajo de EMA lenta
        """

        if not fast_values or not slow_values:
            return 0

        latest_direction = self._compare(
            fast=fast_values[-1],
            slow=slow_values[-1],
        )

        if latest_direction == 0:
            return 0

        count = 0

        for fast, slow in zip(
            reversed(fast_values),
            reversed(slow_values),
        ):
            direction = self._compare(
                fast=fast,
                slow=slow,
            )

            if direction != latest_direction:
                break

            count += 1

        return count

    def _compare(
        self,
        fast: float,
        slow: float,
    ) -> int:
        """
        Compara EMA rápida contra EMA lenta.

        Returns
        -------
        1:
            EMA rápida encima de EMA lenta.
        -1:
            EMA rápida debajo de EMA lenta.
        0:
            EMAs iguales.
        """

        if fast > slow:
            return 1

        if fast < slow:
            return -1

        return 0
