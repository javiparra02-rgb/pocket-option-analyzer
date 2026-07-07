from pocket_option_analyzer.domain.indicators import EmaSnapshotBuilder
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

    builder = EmaSnapshotBuilder()

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


def test_build_detects_bullish_ema_alignment() -> None:

    builder = EmaSnapshotBuilder()

    series = _series_from_closes(
        closes=tuple(
            float(value)
            for value in range(
                100,
                120,
            )
        ),
    )

    result = builder.build(
        series=series,
        profile=StrategyProfile.otc_precision_10s(),
    )

    assert result is not None
    assert result.is_bullish_alignment is True
    assert result.is_bearish_alignment is False
    assert result.separation_candles >= 3


def test_build_detects_bearish_ema_alignment() -> None:

    builder = EmaSnapshotBuilder()

    series = _series_from_closes(
        closes=tuple(
            float(value)
            for value in range(
                120,
                100,
                -1,
            )
        ),
    )

    result = builder.build(
        series=series,
        profile=StrategyProfile.otc_precision_10s(),
    )

    assert result is not None
    assert result.is_bullish_alignment is False
    assert result.is_bearish_alignment is True
    assert result.separation_candles >= 3


def test_build_returns_zero_separation_when_emas_are_equal() -> None:

    builder = EmaSnapshotBuilder()

    series = _series_from_closes(
        closes=tuple(
            100.0
            for _ in range(20)
        ),
    )

    result = builder.build(
        series=series,
        profile=StrategyProfile.otc_precision_10s(),
    )

    assert result is not None
    assert result.is_bullish_alignment is False
    assert result.is_bearish_alignment is False
    assert result.separation_candles == 0