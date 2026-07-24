from pocket_option_analyzer.application.market import (
    VisualPriceSeriesBuilder,
)
from pocket_option_analyzer.vision.models import (
    CandleCandidate,
    CandleGeometry,
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
    geometry: CandleGeometry | None = None,
) -> ClassifiedCandle:

    return ClassifiedCandle(
        candidate=CandleCandidate(
            x=x,
            y=y,
            width=width,
            height=height,
            area=width * height,
            geometry=geometry,
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
                y=10,
                width=21,
                height=61,
                candle_type=CandleType.BULLISH,
                geometry=CandleGeometry(
                    high_y=10,
                    body_top_y=25,
                    body_bottom_y=55,
                    low_y=70,
                ),
            ),
        ),
    )

    result = builder.build(
        series=series,
    )

    candle = result.latest

    assert candle is not None
    assert candle.open == 15.0
    assert candle.high == 60.0
    assert candle.low == 0.0
    assert candle.close == 45.0

    assert candle.is_bullish is True
    assert candle.body_size == 30.0
    assert candle.upper_wick_size == 15.0
    assert candle.lower_wick_size == 15.0


def test_visual_price_series_builder_converts_bearish_candle() -> None:

    builder = VisualPriceSeriesBuilder()

    series = CandleSeries(
        candles=(
            _classified_candle(
                x=10,
                y=10,
                width=21,
                height=61,
                candle_type=CandleType.BEARISH,
                geometry=CandleGeometry(
                    high_y=10,
                    body_top_y=25,
                    body_bottom_y=55,
                    low_y=70,
                ),
            ),
        ),
    )

    result = builder.build(
        series=series,
    )

    candle = result.latest

    assert candle is not None
    assert candle.open == 45.0
    assert candle.high == 60.0
    assert candle.low == 0.0
    assert candle.close == 15.0

    assert candle.is_bearish is True
    assert candle.body_size == 30.0
    assert candle.upper_wick_size == 15.0
    assert candle.lower_wick_size == 15.0


def test_visual_price_series_builder_converts_doji_candle() -> None:

    builder = VisualPriceSeriesBuilder()

    series = CandleSeries(
        candles=(
            _classified_candle(
                x=10,
                y=10,
                width=21,
                height=61,
                candle_type=CandleType.DOJI,
                geometry=CandleGeometry(
                    high_y=10,
                    body_top_y=39,
                    body_bottom_y=41,
                    low_y=70,
                ),
            ),
        ),
    )

    result = builder.build(
        series=series,
    )

    candle = result.latest

    assert candle is not None
    assert candle.open == 30.0
    assert candle.high == 60.0
    assert candle.low == 0.0
    assert candle.close == 30.0

    assert candle.is_doji is True
    assert candle.upper_wick_size == 30.0
    assert candle.lower_wick_size == 30.0


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


def test_visual_price_series_builder_uses_shared_chart_bottom() -> None:

    builder = VisualPriceSeriesBuilder()

    upper_candle = _classified_candle(
        x=10,
        y=10,
        width=21,
        height=61,
        candle_type=CandleType.BULLISH,
        geometry=CandleGeometry(
            high_y=10,
            body_top_y=25,
            body_bottom_y=55,
            low_y=70,
        ),
    )
    lower_candle = _classified_candle(
        x=40,
        y=30,
        width=21,
        height=61,
        candle_type=CandleType.BEARISH,
        geometry=CandleGeometry(
            high_y=30,
            body_top_y=45,
            body_bottom_y=75,
            low_y=90,
        ),
    )

    result = builder.build(
        series=CandleSeries(
            candles=(
                lower_candle,
                upper_candle,
            ),
        ),
    )

    assert len(result) == 2

    first = result.candles[0]
    second = result.candles[1]

    assert first.high == 80.0
    assert first.low == 20.0
    assert first.open == 35.0
    assert first.close == 65.0

    assert second.high == 60.0
    assert second.low == 0.0
    assert second.open == 45.0
    assert second.close == 15.0


def test_visual_price_series_builder_falls_back_when_geometry_is_missing() -> None:

    builder = VisualPriceSeriesBuilder()

    series = CandleSeries(
        candles=(
            _classified_candle(
                x=10,
                y=40,
                width=5,
                height=20,
                candle_type=CandleType.BULLISH,
                geometry=None,
            ),
        ),
    )

    result = builder.build(
        series=series,
    )

    candle = result.latest

    assert candle is not None
    assert candle.open == 0.0
    assert candle.high == 20.0
    assert candle.low == 0.0
    assert candle.close == 20.0