from pocket_option_analyzer.vision.models import (
    CandleCandidate,
    CandleColor,
    CandleType,
    ClassifiedCandle,
)
from pocket_option_analyzer.vision.services import (
    CandleSeriesBuilder,
)


def test_build_orders_candles_by_x_position() -> None:

    newest_candle = ClassifiedCandle(
        candidate=CandleCandidate(
            x=30,
            y=20,
            width=5,
            height=30,
            area=150,
            color=CandleColor.RED,
        ),
        candle_type=CandleType.BEARISH,
    )

    oldest_candle = ClassifiedCandle(
        candidate=CandleCandidate(
            x=10,
            y=20,
            width=5,
            height=30,
            area=150,
            color=CandleColor.GREEN,
        ),
        candle_type=CandleType.BULLISH,
    )

    builder = CandleSeriesBuilder()

    series = builder.build(
        [
            newest_candle,
            oldest_candle,
        ]
    )

    assert series.first is oldest_candle
    assert series.latest is newest_candle


def _classified(
    x: int,
    candle_type: CandleType,
) -> ClassifiedCandle:

    return ClassifiedCandle(
        candidate=CandleCandidate(
            x=x,
            y=10,
            width=10,
            height=40,
            area=400,
        ),
        candle_type=candle_type,
    )


def test_candle_series_builder_orders_candles_from_left_to_right() -> None:

    builder = CandleSeriesBuilder()

    right = _classified(
        x=100,
        candle_type=CandleType.BEARISH,
    )

    left = _classified(
        x=10,
        candle_type=CandleType.BULLISH,
    )

    series = builder.build(
        [
            right,
            left,
        ],
    )

    assert series.candles == (
        left,
        right,
    )
    assert series.latest is right
