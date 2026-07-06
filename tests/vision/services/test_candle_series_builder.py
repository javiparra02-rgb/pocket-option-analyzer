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