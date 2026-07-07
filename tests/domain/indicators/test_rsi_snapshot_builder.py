from pocket_option_analyzer.domain.indicators import RsiSnapshotBuilder
from pocket_option_analyzer.domain.market import (
    PriceCandle,
    PriceSeries,
)
from pocket_option_analyzer.domain.strategy import StrategyProfile


def _series_from_closes(
    closes: tuple[float, ...],
) -> PriceSeries:

    return PriceSeries(
        candles=tuple(
            PriceCandle(
                open=close - 1,
                high=close + 2,
                low=close - 2,
                close=close,
            )
            for close in closes
        ),
    )


def test_build_returns_none_when_not_enough_values() -> None:

    builder = RsiSnapshotBuilder()

    series = _series_from_closes(
        closes=(
            100.0,
            101.0,
            102.0,
        ),
    )

    result = builder.build(
        series=series,
        profile=StrategyProfile.otc_precision_10s(),
    )

    assert result is None


def test_build_returns_latest_rsi_value_for_rising_prices() -> None:

    builder = RsiSnapshotBuilder()

    series = _series_from_closes(
        closes=(
            100.0,
            101.0,
            102.0,
            103.0,
            104.0,
            105.0,
            106.0,
            107.0,
        ),
    )

    result = builder.build(
        series=series,
        profile=StrategyProfile.otc_precision_10s(),
    )

    assert result is not None
    assert result.value == 100.0


def test_build_returns_latest_rsi_value_for_flat_prices() -> None:

    builder = RsiSnapshotBuilder()

    series = _series_from_closes(
        closes=tuple(
            100.0
            for _ in range(8)
        ),
    )

    result = builder.build(
        series=series,
        profile=StrategyProfile.otc_precision_10s(),
    )

    assert result is not None
    assert result.value == 50.0