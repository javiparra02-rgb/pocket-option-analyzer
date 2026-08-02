from pocket_option_analyzer.domain.market import (
    PriceCandle,
    PriceSeries,
)


def _candle(
    close: float,
) -> PriceCandle:

    return PriceCandle(
        open=close - 1,
        high=close + 2,
        low=close - 2,
        close=close,
    )


def test_price_series_exposes_latest_candle() -> None:

    first = _candle(100.0)
    latest = _candle(105.0)

    series = PriceSeries(
        candles=(
            first,
            latest,
        ),
    )

    assert len(series) == 2
    assert series.latest is latest


def test_price_series_exposes_price_vectors() -> None:

    series = PriceSeries(
        candles=(
            _candle(100.0),
            _candle(105.0),
        ),
    )

    assert series.closes == (
        100.0,
        105.0,
    )
    assert series.highs == (
        102.0,
        107.0,
    )
    assert series.lows == (
        98.0,
        103.0,
    )


def test_price_series_can_return_last_candles() -> None:

    series = PriceSeries(
        candles=(
            _candle(100.0),
            _candle(101.0),
            _candle(102.0),
        ),
    )

    result = series.last(2)

    assert len(result) == 2
    assert result.closes == (
        101.0,
        102.0,
    )
