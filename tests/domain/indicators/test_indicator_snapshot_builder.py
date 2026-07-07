from pocket_option_analyzer.domain.indicators import (
    EmaSnapshot,
    IndicatorSnapshotBuilder,
    RsiSnapshot,
    StochasticSnapshot,
)
from pocket_option_analyzer.domain.market import (
    PriceCandle,
    PriceSeries,
)
from pocket_option_analyzer.domain.strategy import StrategyProfile


class FakeSnapshotBuilder:

    def __init__(
        self,
        result,
    ) -> None:
        self.result = result

    def build(
        self,
        series,
        profile,
    ):
        return self.result


def _series() -> PriceSeries:

    return PriceSeries(
        candles=(
            PriceCandle(
                open=100.0,
                high=105.0,
                low=95.0,
                close=102.0,
            ),
            PriceCandle(
                open=102.0,
                high=106.0,
                low=98.0,
                close=104.0,
            ),
        ),
    )


def test_build_returns_complete_indicator_snapshot() -> None:

    ema = EmaSnapshot(
        fast_value=105.0,
        slow_value=100.0,
        separation_candles=3,
    )

    rsi = RsiSnapshot(
        value=57.0,
    )

    stochastic = StochasticSnapshot(
        k_previous=18.0,
        d_previous=20.0,
        k_value=24.0,
        d_value=21.0,
    )

    builder = IndicatorSnapshotBuilder(
        ema_builder=FakeSnapshotBuilder(ema),
        rsi_builder=FakeSnapshotBuilder(rsi),
        stochastic_builder=FakeSnapshotBuilder(stochastic),
    )

    result = builder.build(
        series=_series(),
        profile=StrategyProfile.otc_precision_10s(),
    )

    assert result is not None
    assert result.ema is ema
    assert result.rsi is rsi
    assert result.stochastic is stochastic


def test_build_returns_none_when_ema_is_missing() -> None:

    builder = IndicatorSnapshotBuilder(
        ema_builder=FakeSnapshotBuilder(None),
        rsi_builder=FakeSnapshotBuilder(
            RsiSnapshot(
                value=57.0,
            ),
        ),
        stochastic_builder=FakeSnapshotBuilder(
            StochasticSnapshot(
                k_previous=18.0,
                d_previous=20.0,
                k_value=24.0,
                d_value=21.0,
            ),
        ),
    )

    result = builder.build(
        series=_series(),
        profile=StrategyProfile.otc_precision_10s(),
    )

    assert result is None


def test_build_returns_none_when_rsi_is_missing() -> None:

    builder = IndicatorSnapshotBuilder(
        ema_builder=FakeSnapshotBuilder(
            EmaSnapshot(
                fast_value=105.0,
                slow_value=100.0,
                separation_candles=3,
            ),
        ),
        rsi_builder=FakeSnapshotBuilder(None),
        stochastic_builder=FakeSnapshotBuilder(
            StochasticSnapshot(
                k_previous=18.0,
                d_previous=20.0,
                k_value=24.0,
                d_value=21.0,
            ),
        ),
    )

    result = builder.build(
        series=_series(),
        profile=StrategyProfile.otc_precision_10s(),
    )

    assert result is None


def test_build_returns_none_when_stochastic_is_missing() -> None:

    builder = IndicatorSnapshotBuilder(
        ema_builder=FakeSnapshotBuilder(
            EmaSnapshot(
                fast_value=105.0,
                slow_value=100.0,
                separation_candles=3,
            ),
        ),
        rsi_builder=FakeSnapshotBuilder(
            RsiSnapshot(
                value=57.0,
            ),
        ),
        stochastic_builder=FakeSnapshotBuilder(None),
    )

    result = builder.build(
        series=_series(),
        profile=StrategyProfile.otc_precision_10s(),
    )

    assert result is None