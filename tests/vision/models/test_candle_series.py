from pocket_option_analyzer.vision.models import (
    CandleCandidate,
    CandleColor,
    CandleSeries,
    CandleType,
    ClassifiedCandle,
)


def test_candle_series_exposes_first_and_latest() -> None:

    first_candle = ClassifiedCandle(
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

    latest_candle = ClassifiedCandle(
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

    series = CandleSeries(
        candles=(
            first_candle,
            latest_candle,
        ),
    )

    assert len(series) == 2
    assert series.first is first_candle
    assert series.latest is latest_candle