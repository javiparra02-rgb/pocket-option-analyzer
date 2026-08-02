from pocket_option_analyzer.vision.models import (
    CandleCandidate,
)
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


def test_candle_filter_keeps_short_bodies_and_dojis() -> None:

    tall = _candidate(
        x=10,
        y=20,
        width=60,
        height=80,
        area=4800,
    )
    short = _candidate(
        x=80,
        y=40,
        width=59,
        height=5,
        area=295,
    )
    doji = _candidate(
        x=150,
        y=50,
        width=58,
        height=1,
        area=58,
    )

    result = CandleFilter().filter(
        [
            doji,
            tall,
            short,
        ],
    )

    assert result == [
        tall,
        short,
        doji,
    ]


def test_candle_filter_removes_narrow_text_using_dominant_width() -> None:

    first = _candidate(
        x=10,
        y=100,
        width=58,
        height=60,
        area=3480,
    )
    second = _candidate(
        x=80,
        y=120,
        width=60,
        height=25,
        area=1500,
    )
    third = _candidate(
        x=150,
        y=110,
        width=59,
        height=8,
        area=472,
    )
    text_fragment = _candidate(
        x=45,
        y=20,
        width=12,
        height=20,
        area=240,
    )

    result = CandleFilter().filter(
        [
            text_fragment,
            third,
            first,
            second,
        ],
    )

    assert result == [
        first,
        second,
        third,
    ]


def test_candle_filter_keeps_partial_edge_candle() -> None:

    partial = _candidate(
        x=0,
        y=100,
        width=40,
        height=70,
        area=2800,
    )
    first_complete = _candidate(
        x=60,
        y=110,
        width=59,
        height=60,
        area=3540,
    )
    second_complete = _candidate(
        x=125,
        y=120,
        width=60,
        height=45,
        area=2700,
    )

    result = CandleFilter().filter(
        [
            second_complete,
            partial,
            first_complete,
        ],
    )

    assert result == [
        partial,
        first_complete,
        second_complete,
    ]


def test_candle_filter_prefers_wider_candle_group_over_narrow_text() -> None:

    candles = [
        _candidate(
            x=20 + index * 60,
            y=100,
            width=50,
            height=60,
            area=3000,
        )
        for index in range(12)
    ]

    text_fragments = [
        _candidate(
            x=5 + index * 15,
            y=20,
            width=10,
            height=18,
            area=180,
        )
        for index in range(30)
    ]

    result = CandleFilter().filter(
        [
            *text_fragments,
            *candles,
        ],
    )

    assert result == candles


def test_candle_filter_merges_vertically_split_candle() -> None:

    upper_fragment = _candidate(
        x=100,
        y=20,
        width=50,
        height=35,
        area=1750,
    )
    lower_fragment = _candidate(
        x=100,
        y=60,
        width=50,
        height=40,
        area=2000,
    )
    second_candle = _candidate(
        x=160,
        y=30,
        width=50,
        height=70,
        area=3500,
    )

    result = CandleFilter().filter(
        [
            lower_fragment,
            second_candle,
            upper_fragment,
        ],
    )

    assert len(result) == 2

    assert result[0] == CandleCandidate(
        x=100,
        y=20,
        width=50,
        height=80,
        area=4000,
    )
    assert result[1] == second_candle


def test_candle_filter_does_not_merge_neighboring_candles() -> None:

    first = _candidate(
        x=100,
        y=20,
        width=50,
        height=80,
        area=4000,
    )
    second = _candidate(
        x=155,
        y=30,
        width=50,
        height=70,
        area=3500,
    )

    result = CandleFilter().filter(
        [
            second,
            first,
        ],
    )

    assert result == [
        first,
        second,
    ]
