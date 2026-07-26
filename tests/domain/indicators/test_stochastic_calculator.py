import pytest

from pocket_option_analyzer.domain.indicators import StochasticCalculator


def test_stochastic_calculator_returns_empty_tuple_when_not_enough_values() -> None:

    calculator = StochasticCalculator()

    k_values, d_values = calculator.calculate(
        highs=(
            102.0,
            103.0,
        ),
        lows=(
            98.0,
            99.0,
        ),
        closes=(
            100.0,
            101.0,
        ),
        k_period=3,
        d_period=2,
        smooth_period=1,
    )

    assert k_values == ()
    assert d_values == ()


def test_stochastic_calculator_calculates_k_and_d_values() -> None:

    calculator = StochasticCalculator()

    k_values, d_values = calculator.calculate(
        highs=(
            12.0,
            13.0,
            14.0,
            15.0,
        ),
        lows=(
            9.0,
            10.0,
            11.0,
            12.0,
        ),
        closes=(
            11.0,
            12.0,
            13.0,
            14.0,
        ),
        k_period=3,
        d_period=2,
        smooth_period=1,
    )

    assert k_values == (
        80.0,
        80.0,
    )
    assert d_values == (
        80.0,
    )


def test_stochastic_calculator_returns_50_when_range_is_zero() -> None:

    calculator = StochasticCalculator()

    k_values, d_values = calculator.calculate(
        highs=(
            100.0,
            100.0,
            100.0,
        ),
        lows=(
            100.0,
            100.0,
            100.0,
        ),
        closes=(
            100.0,
            100.0,
            100.0,
        ),
        k_period=3,
        d_period=1,
        smooth_period=1,
    )

    assert k_values == (
        50.0,
    )
    assert d_values == (
        50.0,
    )


def test_stochastic_calculator_applies_smoothing() -> None:

    calculator = StochasticCalculator()

    k_values, d_values = calculator.calculate(
        highs=(
            12.0,
            13.0,
            14.0,
            15.0,
            16.0,
        ),
        lows=(
            9.0,
            10.0,
            11.0,
            12.0,
            13.0,
        ),
        closes=(
            11.0,
            12.0,
            13.0,
            14.0,
            15.0,
        ),
        k_period=3,
        d_period=2,
        smooth_period=2,
    )

    assert k_values == (
        80.0,
        80.0,
    )
    assert d_values == (
        80.0,
    )


def test_stochastic_calculator_rejects_invalid_periods() -> None:

    calculator = StochasticCalculator()

    with pytest.raises(
        ValueError,
        match="Stochastic K period must be greater than zero.",
    ):
        calculator.calculate(
            highs=(1.0,),
            lows=(1.0,),
            closes=(1.0,),
            k_period=0,
            d_period=1,
            smooth_period=1,
        )


def test_stochastic_calculator_rejects_mismatched_lengths() -> None:

    calculator = StochasticCalculator()

    with pytest.raises(
        ValueError,
        match="High, low and close sequences must have the same length.",
    ):
        calculator.calculate(
            highs=(
                1.0,
                2.0,
            ),
            lows=(1.0,),
            closes=(
                1.0,
                2.0,
            ),
            k_period=1,
            d_period=1,
            smooth_period=1,
        )


def test_stochastic_calculator_returns_latest_window_diagnostics() -> None:

    calculator = StochasticCalculator()

    (
        k_values,
        d_values,
        diagnostics,
    ) = calculator.calculate_with_diagnostics(
        highs=(
            12.0,
            13.0,
            14.0,
            15.0,
            16.0,
        ),
        lows=(
            9.0,
            10.0,
            11.0,
            12.0,
            13.0,
        ),
        closes=(
            11.0,
            12.0,
            13.0,
            14.0,
            15.0,
        ),
        k_period=3,
        d_period=2,
        smooth_period=2,
    )

    assert k_values == (
        80.0,
        80.0,
    )
    assert d_values == (
        80.0,
    )

    assert diagnostics is not None
    assert diagnostics.source_candle_count == 5
    assert diagnostics.k_period == 3
    assert diagnostics.highest_high == 16.0
    assert diagnostics.lowest_low == 11.0
    assert diagnostics.latest_close == 15.0
    assert diagnostics.latest_raw_k == 80.0
    assert diagnostics.latest_smoothed_k == 80.0
    assert diagnostics.latest_d == 80.0


def test_stochastic_calculator_diagnostics_use_50_for_flat_window() -> None:

    calculator = StochasticCalculator()

    (
        _,
        _,
        diagnostics,
    ) = calculator.calculate_with_diagnostics(
        highs=(
            100.0,
            100.0,
            100.0,
        ),
        lows=(
            100.0,
            100.0,
            100.0,
        ),
        closes=(
            100.0,
            100.0,
            100.0,
        ),
        k_period=3,
        d_period=1,
        smooth_period=1,
    )

    assert diagnostics is not None
    assert diagnostics.price_range == 0.0
    assert diagnostics.latest_raw_k == 50.0
    assert diagnostics.latest_smoothed_k == 50.0
    assert diagnostics.latest_d == 50.0