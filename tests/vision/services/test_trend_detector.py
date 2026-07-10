from pocket_option_analyzer.vision.models import (
    CandleCandidate,
    CandleSeries,
    CandleType,
    ClassifiedCandle,
    TrendDirection,
)
from pocket_option_analyzer.vision.services import TrendDetector


def _candle(
    x: int,
    center_y: int,
    candle_type: CandleType,
) -> ClassifiedCandle:

    return ClassifiedCandle(
        candidate=CandleCandidate(
            x=x,
            y=center_y - 10,
            width=8,
            height=20,
            area=160,
        ),
        candle_type=candle_type,
    )


def _series(
    candles,
) -> CandleSeries:

    return CandleSeries(
        candles=tuple(
            candles,
        ),
    )


def test_trend_detector_returns_unknown_for_empty_series() -> None:

    detector = TrendDetector()

    result = detector.detect(
        series=_series(
            [],
        ),
    )

    assert result is TrendDirection.UNKNOWN


def test_trend_detector_detects_bullish_recent_visual_movement() -> None:

    detector = TrendDetector()

    result = detector.detect(
        series=_series(
            [
                _candle(1, 120, CandleType.BULLISH),
                _candle(2, 110, CandleType.BULLISH),
                _candle(3, 100, CandleType.BEARISH),
                _candle(4, 90, CandleType.BULLISH),
                _candle(5, 80, CandleType.BULLISH),
            ],
        ),
    )

    assert result is TrendDirection.BULLISH


def test_trend_detector_detects_bearish_recent_visual_movement() -> None:

    detector = TrendDetector()

    result = detector.detect(
        series=_series(
            [
                _candle(1, 80, CandleType.BEARISH),
                _candle(2, 90, CandleType.BEARISH),
                _candle(3, 100, CandleType.BULLISH),
                _candle(4, 115, CandleType.BEARISH),
                _candle(5, 130, CandleType.BEARISH),
            ],
        ),
    )

    assert result is TrendDirection.BEARISH


def test_trend_detector_detects_bearish_when_recent_drop_is_strong() -> None:

    detector = TrendDetector()

    result = detector.detect(
        series=_series(
            [
                _candle(1, 70, CandleType.BULLISH),
                _candle(2, 85, CandleType.BEARISH),
                _candle(3, 105, CandleType.BEARISH),
                _candle(4, 130, CandleType.BEARISH),
                _candle(5, 160, CandleType.BEARISH),
            ],
        ),
    )

    assert result is TrendDirection.BEARISH


def test_trend_detector_returns_sideways_when_no_direction_is_clear() -> None:

    detector = TrendDetector()

    result = detector.detect(
        series=_series(
            [
                _candle(1, 100, CandleType.BULLISH),
                _candle(2, 103, CandleType.BEARISH),
                _candle(3, 101, CandleType.BULLISH),
                _candle(4, 104, CandleType.BEARISH),
                _candle(5, 102, CandleType.DOJI),
            ],
        ),
    )

    assert result is TrendDirection.SIDEWAYS


def test_trend_detector_ignores_unknown_recent_candles() -> None:

    detector = TrendDetector()

    result = detector.detect(
        series=_series(
            [
                _candle(1, 80, CandleType.BEARISH),
                _candle(2, 95, CandleType.BEARISH),
                _candle(3, 110, CandleType.BEARISH),
                _candle(4, 125, CandleType.UNKNOWN),
                _candle(5, 130, CandleType.UNKNOWN),
            ],
        ),
    )

    assert result is TrendDirection.BEARISH