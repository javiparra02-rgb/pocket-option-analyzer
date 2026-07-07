import pytest

from pocket_option_analyzer.domain.indicators import RsiCalculator


def test_rsi_calculator_returns_empty_tuple_when_not_enough_values() -> None:

    calculator = RsiCalculator()

    result = calculator.calculate(
        values=(
            100.0,
            101.0,
            102.0,
        ),
        period=3,
    )

    assert result == ()


def test_rsi_calculator_returns_100_when_all_values_are_rising() -> None:

    calculator = RsiCalculator()

    result = calculator.calculate(
        values=(
            100.0,
            101.0,
            102.0,
            103.0,
        ),
        period=3,
    )

    assert result == (
        100.0,
    )


def test_rsi_calculator_returns_0_when_all_values_are_falling() -> None:

    calculator = RsiCalculator()

    result = calculator.calculate(
        values=(
            103.0,
            102.0,
            101.0,
            100.0,
        ),
        period=3,
    )

    assert result == (
        0.0,
    )


def test_rsi_calculator_returns_50_when_values_are_flat() -> None:

    calculator = RsiCalculator()

    result = calculator.calculate(
        values=(
            100.0,
            100.0,
            100.0,
            100.0,
        ),
        period=3,
    )

    assert result == (
        50.0,
    )


def test_rsi_calculator_calculates_multiple_values() -> None:

    calculator = RsiCalculator()

    result = calculator.calculate(
        values=(
            100.0,
            102.0,
            101.0,
            103.0,
            104.0,
        ),
        period=3,
    )

    assert len(result) == 2
    assert round(result[0], 2) == 80.0
    assert round(result[1], 2) == 84.62


def test_rsi_calculator_rejects_invalid_period() -> None:

    calculator = RsiCalculator()

    with pytest.raises(
        ValueError,
        match="RSI period must be greater than zero.",
    ):
        calculator.calculate(
            values=(
                100.0,
                101.0,
            ),
            period=0,
        )