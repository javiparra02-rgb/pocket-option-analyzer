from pocket_option_analyzer.vision.models import (
    CandleCandidate,
    CandleColor,
    CandleSeries,
    CandleType,
    ClassifiedCandle,
    TrendDirection,
)
from pocket_option_analyzer.vision.services import TrendDetector


def _classified_candle(
    x: int,
    candle_type: CandleType,
) -> ClassifiedCandle:

    return ClassifiedCandle(
        candidate=CandleCandidate(
            x=x,
            y=20,
            width=5,
            height=30,
            area=150,
            color=CandleColor.UNKNOWN,
        ),
        candle_type=candle_type,
    )


def test_detect_returns_unknown_when_series_has_not_enough_candles() -> None:

    series = CandleSeries(
        candles=(
            _classified_candle(
                x=10,
                candle_type=CandleType.BULLISH,
            ),
        ),
    )

    detector = TrendDetector()

    result = detector.detect(series)

    assert result is TrendDirection.UNKNOWN


def test_detect_returns_bullish_when_bullish_candles_dominate() -> None:

    series = CandleSeries(
        candles=(
            _classified_candle(
                x=10,
                candle_type=CandleType.BULLISH,
            ),
            _classified_candle(
                x=20,
                candle_type=CandleType.BULLISH,
            ),
            _classified_candle(
                x=30,
                candle_type=CandleType.BEARISH,
            ),
        ),
    )

    detector = TrendDetector()

    result = detector.detect(series)

    assert result is TrendDirection.BULLISH


def test_detect_returns_bearish_when_bearish_candles_dominate() -> None:

    series = CandleSeries(
        candles=(
            _classified_candle(
                x=10,
                candle_type=CandleType.BEARISH,
            ),
            _classified_candle(
                x=20,
                candle_type=CandleType.BEARISH,
            ),
            _classified_candle(
                x=30,
                candle_type=CandleType.BULLISH,
            ),
        ),
    )

    detector = TrendDetector()

    result = detector.detect(series)

    assert result is TrendDirection.BEARISH


def test_detect_returns_sideways_when_no_direction_dominates() -> None:

    series = CandleSeries(
        candles=(
            _classified_candle(
                x=10,
                candle_type=CandleType.BULLISH,
            ),
            _classified_candle(
                x=20,
                candle_type=CandleType.BEARISH,
            ),
            _classified_candle(
                x=30,
                candle_type=CandleType.BULLISH,
            ),
            _classified_candle(
                x=40,
                candle_type=CandleType.BEARISH,
            ),
        ),
    )

    detector = TrendDetector()

    result = detector.detect(series)

    assert result is TrendDirection.SIDEWAYS