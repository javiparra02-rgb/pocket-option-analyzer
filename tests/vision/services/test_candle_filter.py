from pocket_option_analyzer.vision.models import CandleCandidate
from pocket_option_analyzer.vision.services import CandleFilter


def _candidate(
    x: int,
    y: int,
    width: int,
    height: int,
    area: int,
) -> CandleCandidate:

    return CandleCandidate(
        x=x,
        y=y,
        width=width,
        height=height,
        area=area,
    )


def test_candle_filter_keeps_candle_like_candidates() -> None:

    candidate = _candidate(
        x=10,
        y=20,
        width=10,
        height=60,
        area=600,
    )

    result = CandleFilter().filter(
        [
            candidate,
        ],
    )

    assert result == [
        candidate,
    ]


def test_candle_filter_removes_small_text_like_candidates() -> None:

    valid = _candidate(
        x=10,
        y=20,
        width=10,
        height=60,
        area=600,
    )

    small_text = _candidate(
        x=30,
        y=20,
        width=4,
        height=8,
        area=32,
    )

    result = CandleFilter().filter(
        [
            valid,
            small_text,
        ],
    )

    assert result == [
        valid,
    ]


def test_candle_filter_removes_wide_label_like_candidates() -> None:

    valid = _candidate(
        x=10,
        y=20,
        width=10,
        height=60,
        area=600,
    )

    wide_label = _candidate(
        x=30,
        y=20,
        width=140,
        height=20,
        area=2800,
    )

    result = CandleFilter().filter(
        [
            valid,
            wide_label,
        ],
    )

    assert result == [
        valid,
    ]


def test_candle_filter_orders_candidates_from_left_to_right() -> None:

    left = _candidate(
        x=10,
        y=20,
        width=10,
        height=60,
        area=600,
    )

    right = _candidate(
        x=80,
        y=20,
        width=10,
        height=60,
        area=600,
    )

    result = CandleFilter().filter(
        [
            right,
            left,
        ],
    )

    assert result == [
        left,
        right,
    ]