from __future__ import annotations

import pytest

from pocket_option_analyzer.domain.indicators import (
    StochasticCalculationDiagnostics,
)


def test_stochastic_diagnostics_calculates_price_range() -> None:

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

    assert diagnostics.price_range == 40.0


def test_stochastic_diagnostics_rejects_invalid_high_low_order() -> None:

    with pytest.raises(
        ValueError,
        match="highest_high no puede ser menor",
    ):
        StochasticCalculationDiagnostics(
            source_candle_count=17,
            k_period=5,
            highest_high=80.0,
            lowest_low=120.0,
            latest_close=100.0,
            latest_raw_k=50.0,
            latest_smoothed_k=50.0,
            latest_d=50.0,
        )
