from pocket_option_analyzer.domain.market import PriceCandle


def test_price_candle_detects_bullish_direction() -> None:

    candle = PriceCandle(
        open=100.0,
        high=110.0,
        low=95.0,
        close=108.0,
    )

    assert candle.is_bullish is True
    assert candle.is_bearish is False
    assert candle.is_doji is False


def test_price_candle_detects_bearish_direction() -> None:

    candle = PriceCandle(
        open=108.0,
        high=110.0,
        low=95.0,
        close=100.0,
    )

    assert candle.is_bullish is False
    assert candle.is_bearish is True
    assert candle.is_doji is False


def test_price_candle_calculates_body_and_wicks() -> None:

    candle = PriceCandle(
        open=100.0,
        high=110.0,
        low=95.0,
        close=108.0,
    )

    assert candle.total_range == 15.0
    assert candle.body_size == 8.0
    assert candle.upper_wick_size == 2.0
    assert candle.lower_wick_size == 5.0
