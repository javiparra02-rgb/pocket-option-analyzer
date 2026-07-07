import pytest

from pocket_option_analyzer.domain.indicators import EmaCalculator


def test_ema_calculator_returns_empty_tuple_when_not_enough_values() -> None:

    calculator = EmaCalculator()

    result = calculator.calculate(
        values=(
            100.0,
            101.0,
        ),
        period=3,
    )

    assert result == ()


def test_ema_calculator_uses_sma_as_first_ema() -> None:

    calculator = EmaCalculator()

    result = calculator.calculate(
        values=(
            100.0,
            101.0,
            102.0,
        ),
        period=3,
    )

    assert result == (
        101.0,
    )


def test_ema_calculator_calculates_exponential_values() -> None:

    calculator = EmaCalculator()

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
        101.0,
        102.0,
    )


def test_ema_calculator_rejects_invalid_period() -> None:

    calculator = EmaCalculator()

    with pytest.raises(
        ValueError,
        match="EMA period must be greater than zero.",
    ):
        calculator.calculate(
            values=(
                100.0,
                101.0,
            ),
            period=0,
        )