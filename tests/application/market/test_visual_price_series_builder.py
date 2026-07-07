from pocket_option_analyzer.application.market import (
    VisualPriceSeriesBuilder,
)
from pocket_option_analyzer.vision.models import (
    CandleCandidate,
    CandleSeries,
    CandleType,
    ClassifiedCandle,
)


def _classified_candle(
    x: int,
    y: int,
    width: int,
    height: int,
    candle_type: CandleType,
) -> ClassifiedCandle:

    return ClassifiedCandle(
        candidate=CandleCandidate(
            x=x,
            y=y,
            width=width,
            height=height,
            area=width * height,
        ),
        candle_type=candle_type,
    )


def test_visual_price_series_builder_orders_candles_by_x_position() -> None:

    builder = VisualPriceSeriesBuilder()

    series = CandleSeries(
        candles=(
            _classified_candle(
                x=30,
                y=40,
                width=5,
                height=20,
                candle_type=CandleType.BULLISH,
            ),
            _classified_candle(
                x=10,
                y=50,
                width=5,
                height=10,
                candle_type=CandleType.BEARISH,
            ),
        ),
    )

    result = builder.build(series)

    assert len(result) == 2
    assert result.candles[0].is_bearish is True
    assert result.candles[1].is_bullish is True


def test_visual_price_series_builder_converts_bullish_candle() -> None:

    builder = VisualPriceSeriesBuilder()

    series = CandleSeries(
        candles=(
            _classified_candle(
                x=10,
                y=40,
                width=5,
                height=20,
                candle_type=CandleType.BULLISH,
            ),
        ),
    )

    result = builder.build(series)

    candle = result.latest

    assert candle is not None
    assert candle.open == 0.0
    assert candle.high == 20.0
    assert candle.low == 0.0
    assert candle.close == 20.0
    assert candle.is_bullish is True


def test_visual_price_series_builder_converts_bearish_candle() -> None:

    builder = VisualPriceSeriesBuilder()

    series = CandleSeries(
        candles=(
            _classified_candle(
                x=10,
                y=40,
                width=5,
                height=20,
                candle_type=CandleType.BEARISH,
            ),
        ),
    )

    result = builder.build(series)

    candle = result.latest

    assert candle is not None
    assert candle.open == 20.0
    assert candle.high == 20.0
    assert candle.low == 0.0
    assert candle.close == 0.0
    assert candle.is_bearish is True


def test_visual_price_series_builder_converts_doji_candle() -> None:

    builder = VisualPriceSeriesBuilder()

    series = CandleSeries(
        candles=(
            _classified_candle(
                x=10,
                y=40,
                width=5,
                height=20,
                candle_type=CandleType.DOJI,
            ),
        ),
    )

    result = builder.build(series)

    candle = result.latest

    assert candle is not None
    assert candle.open == 10.0
    assert candle.high == 20.0
    assert candle.low == 0.0
    assert candle.close == 10.0
    assert candle.is_doji is True


def test_visual_price_series_builder_ignores_unknown_candles() -> None:

    builder = VisualPriceSeriesBuilder()

    series = CandleSeries(
        candles=(
            _classified_candle(
                x=10,
                y=40,
                width=5,
                height=20,
                candle_type=CandleType.UNKNOWN,
            ),
        ),
    )

    result = builder.build(series)

    assert result.is_empty() is True