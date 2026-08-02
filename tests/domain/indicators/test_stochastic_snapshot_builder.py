from pocket_option_analyzer.domain.indicators import (
    StochasticCalculationDiagnostics,
    StochasticSnapshotBuilder,
)
from pocket_option_analyzer.domain.market import (
    PriceCandle,
    PriceSeries,
)
from pocket_option_analyzer.domain.strategy import StrategyProfile


class FakeStochasticCalculator:
    def __init__(
        self,
        k_values: tuple[float, ...],
        d_values: tuple[float, ...],
        diagnostics: (StochasticCalculationDiagnostics | None) = None,
    ) -> None:
        self._k_values = k_values
        self._d_values = d_values
        self._diagnostics = diagnostics

    def calculate_with_diagnostics(
        self,
        highs,
        lows,
        closes,
        k_period,
        d_period,
        smooth_period,
    ):
        return (
            self._k_values,
            self._d_values,
            self._diagnostics,
        )


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


def test_build_returns_none_when_not_enough_values() -> None:

    builder = StochasticSnapshotBuilder(
        calculator=FakeStochasticCalculator(
            k_values=(20.0,),
            d_values=(18.0,),
        ),
    )

    result = builder.build(
        series=_series(),
        profile=StrategyProfile.otc_precision_10s(),
    )

    assert result is None


def test_build_detects_cross_up_snapshot() -> None:

    builder = StochasticSnapshotBuilder(
        calculator=FakeStochasticCalculator(
            k_values=(
                18.0,
                24.0,
            ),
            d_values=(
                20.0,
                21.0,
            ),
        ),
    )

    result = builder.build(
        series=_series(),
        profile=StrategyProfile.otc_precision_10s(),
    )

    assert result is not None
    assert result.k_previous == 18.0
    assert result.d_previous == 20.0
    assert result.k_value == 24.0
    assert result.d_value == 21.0
    assert result.crossed_up is True
    assert result.crossed_down is False


def test_build_detects_cross_down_snapshot() -> None:

    builder = StochasticSnapshotBuilder(
        calculator=FakeStochasticCalculator(
            k_values=(
                82.0,
                76.0,
            ),
            d_values=(
                80.0,
                78.0,
            ),
        ),
    )

    result = builder.build(
        series=_series(),
        profile=StrategyProfile.otc_precision_10s(),
    )

    assert result is not None
    assert result.k_previous == 82.0
    assert result.d_previous == 80.0
    assert result.k_value == 76.0
    assert result.d_value == 78.0
    assert result.crossed_up is False
    assert result.crossed_down is True


def test_build_preserves_stochastic_calculation_diagnostics() -> None:

    diagnostics = StochasticCalculationDiagnostics(
        source_candle_count=17,
        k_period=5,
        highest_high=120.0,
        lowest_low=80.0,
        latest_close=104.0,
        latest_raw_k=60.0,
        latest_smoothed_k=55.0,
        latest_d=50.0,
    )

    builder = StochasticSnapshotBuilder(
        calculator=FakeStochasticCalculator(
            k_values=(
                48.0,
                55.0,
            ),
            d_values=(
                49.0,
                50.0,
            ),
            diagnostics=diagnostics,
        ),
    )

    result = builder.build(
        series=_series(),
        profile=StrategyProfile.otc_precision_10s(),
    )

    assert result is not None
    assert result.diagnostics is diagnostics
