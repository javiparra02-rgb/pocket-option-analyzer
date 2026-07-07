from __future__ import annotations

from pocket_option_analyzer.domain.indicators.ema_snapshot_builder import (
    EmaSnapshotBuilder,
)
from pocket_option_analyzer.domain.indicators.indicator_snapshot import (
    IndicatorSnapshot,
)
from pocket_option_analyzer.domain.indicators.rsi_snapshot_builder import (
    RsiSnapshotBuilder,
)
from pocket_option_analyzer.domain.indicators.stochastic_snapshot_builder import (
    StochasticSnapshotBuilder,
)
from pocket_option_analyzer.domain.market import PriceSeries
from pocket_option_analyzer.domain.strategy import StrategyProfile


class IndicatorSnapshotBuilder:
    """
    Construye un IndicatorSnapshot completo usando una serie OHLC.

    Une:
    - EMA 5/13
    - RSI(7)
    - Stochastic(5,3,3)
    """

    def __init__(
        self,
        ema_builder: EmaSnapshotBuilder | None = None,
        rsi_builder: RsiSnapshotBuilder | None = None,
        stochastic_builder: StochasticSnapshotBuilder | None = None,
    ) -> None:
        self._ema_builder = ema_builder or EmaSnapshotBuilder()
        self._rsi_builder = rsi_builder or RsiSnapshotBuilder()
        self._stochastic_builder = (
            stochastic_builder or StochasticSnapshotBuilder()
        )

    def build(
        self,
        series: PriceSeries,
        profile: StrategyProfile,
    ) -> IndicatorSnapshot | None:
        """
        Construye el snapshot completo.

        Si cualquier indicador no puede calcularse por falta de datos,
        devuelve None.
        """

        ema = self._ema_builder.build(
            series=series,
            profile=profile,
        )

        if ema is None:
            return None

        rsi = self._rsi_builder.build(
            series=series,
            profile=profile,
        )

        if rsi is None:
            return None

        stochastic = self._stochastic_builder.build(
            series=series,
            profile=profile,
        )

        if stochastic is None:
            return None

        return IndicatorSnapshot(
            ema=ema,
            rsi=rsi,
            stochastic=stochastic,
        )