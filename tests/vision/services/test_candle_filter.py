from pocket_option_analyzer.vision.models import (
    CandleCandidate,
    CandleCandidateDecision,
    CandleDimensionRejectionReason,
    CandleWidthDecisionReason,
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


def test_candle_filter_records_stage_diagnostics() -> None:

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

    narrow_candidate = _candidate(
        x=40,
        y=20,
        width=10,
        height=20,
        area=200,
    )

    invalid_dimension_candidate = _candidate(
        x=20,
        y=20,
        width=5,
        height=4,
        area=20,
    )

    candle_filter = CandleFilter()

    result = candle_filter.filter(
        [
            invalid_dimension_candidate,
            narrow_candidate,
            lower_fragment,
            second_candle,
            upper_fragment,
        ]
    )

    diagnostics = candle_filter.last_diagnostics

    assert len(result) == 2

    assert diagnostics is not None

    assert diagnostics.input_count == 5
    assert diagnostics.dimension_valid_count == 4
    assert diagnostics.width_valid_count == 3
    assert diagnostics.merged_count == 2
    assert diagnostics.returned_count == 2

    assert diagnostics.dominant_width == 50.0

    assert diagnostics.rejected_by_dimensions == 1
    assert diagnostics.rejected_by_width == 1
    assert diagnostics.merged_fragments == 1
    assert diagnostics.truncated_count == 0


def test_candle_filter_records_empty_diagnostics() -> None:

    candle_filter = CandleFilter()

    result = candle_filter.filter(
        [],
    )

    diagnostics = candle_filter.last_diagnostics

    assert result == []

    assert diagnostics is not None

    assert diagnostics.input_count == 0
    assert diagnostics.dimension_valid_count == 0
    assert diagnostics.width_valid_count == 0
    assert diagnostics.merged_count == 0
    assert diagnostics.returned_count == 0

    assert diagnostics.dominant_width is None

    assert diagnostics.rejected_by_dimensions == 0
    assert diagnostics.rejected_by_width == 0
    assert diagnostics.merged_fragments == 0
    assert diagnostics.truncated_count == 0


def test_filter_trace_captures_complete_candidate_lifecycle() -> None:
    invalid = _candidate(x=230, y=20, width=5, height=4, area=20)
    narrow = _candidate(x=70, y=20, width=10, height=20, area=200)
    left = _candidate(x=20, y=30, width=50, height=60, area=3000)
    upper = _candidate(x=100, y=20, width=50, height=35, area=1750)
    right = _candidate(x=170, y=30, width=50, height=70, area=3500)
    lower = _candidate(x=100, y=60, width=50, height=40, area=2000)
    result = CandleFilter(max_candidates=2).filter_with_trace(
        [invalid, narrow, left, upper, right, lower]
    )

    assert list(result.candidates) == [
        CandleCandidate(x=100, y=20, width=50, height=80, area=4000),
        right,
    ]
    assert result.candidate_ids == ("merged_000", "candidate_004")
    assert result.trace.dominant_width == 50.0

    traces = {
        candidate.candidate_id: candidate for candidate in result.trace.candidates
    }
    assert traces["candidate_000"].decisions[-1] is (
        CandleCandidateDecision.REJECTED_DIMENSION
    )
    assert traces["candidate_000"].dimension_rejection_reasons == (
        CandleDimensionRejectionReason.AREA_BELOW_MINIMUM,
    )
    assert traces["candidate_001"].decisions[-1] is (
        CandleCandidateDecision.REJECTED_WIDTH
    )
    assert traces["candidate_001"].width_decision_reason is (
        CandleWidthDecisionReason.OUTSIDE_DOMINANT_RANGE
    )
    assert traces["candidate_002"].decisions[-1] is (CandleCandidateDecision.TRUNCATED)
    assert traces["candidate_003"].merged_into == "merged_000"
    assert traces["candidate_005"].merged_into == "merged_000"
    assert traces["merged_000"].merged_from == (
        "candidate_003",
        "candidate_005",
    )
    assert traces["merged_000"].decisions == (
        CandleCandidateDecision.MERGE_RESULT,
        CandleCandidateDecision.RETURNED,
    )
    assert result.trace.merges[0].source_candidate_ids == (
        "candidate_003",
        "candidate_005",
    )
    assert result.trace.merges[0].maximum_center_distance == 10.0
    configuration = result.trace.filter_configuration
    assert configuration is not None
    assert configuration.min_area == 40
    assert configuration.min_relative_width == 0.75
    assert configuration.max_relative_width == 1.30
    assert configuration.max_candidates == 2


def test_filter_trace_candidate_ids_are_stable_for_same_input_order() -> None:
    candidates = [
        _candidate(x=80, y=20, width=10, height=60, area=600),
        _candidate(x=10, y=20, width=10, height=60, area=600),
    ]

    first = CandleFilter().filter_with_trace(candidates)
    second = CandleFilter().filter_with_trace(candidates)

    assert tuple(item.candidate_id for item in first.trace.candidates) == (
        "candidate_000",
        "candidate_001",
    )
    assert (
        first.candidate_ids
        == second.candidate_ids
        == (
            "candidate_001",
            "candidate_000",
        )
    )


def test_filter_result_is_identical_with_and_without_trace_api() -> None:
    candidates = [
        _candidate(x=80, y=20, width=10, height=60, area=600),
        _candidate(x=10, y=20, width=10, height=60, area=600),
    ]

    legacy_result = CandleFilter().filter(candidates)
    traced_result = CandleFilter().filter_with_trace(candidates)

    assert legacy_result == list(traced_result.candidates)


def test_filter_trace_distinguishes_left_edge_width_exception() -> None:
    partial = _candidate(x=0, y=100, width=40, height=70, area=2800)
    complete = (
        _candidate(x=60, y=110, width=59, height=60, area=3540),
        _candidate(x=125, y=120, width=60, height=45, area=2700),
    )

    result = CandleFilter().filter_with_trace([partial, *complete])

    partial_trace = result.trace.candidates[0]
    assert partial_trace.candidate_id == "candidate_000"
    assert partial_trace.width_decision_reason is (
        CandleWidthDecisionReason.LEFT_EDGE_EXCEPTION
    )
    assert partial_trace.decisions[-1] is CandleCandidateDecision.RETURNED
