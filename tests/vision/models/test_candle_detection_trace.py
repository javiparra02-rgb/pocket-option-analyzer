from dataclasses import FrozenInstanceError
from typing import get_type_hints

import pytest

from pocket_option_analyzer.vision.models import (
    CandleCandidateDecision,
    CandleCandidateTrace,
    CandleColor,
    CandleDetectionTrace,
    CandleMergeTrace,
    CandleWidthDecisionReason,
)


def _candidate_trace(
    candidate_id: str = "candidate_000",
) -> CandleCandidateTrace:
    return CandleCandidateTrace(
        candidate_id=candidate_id,
        x=10,
        y=20,
        width=8,
        height=30,
        area=240,
        color=CandleColor.GREEN,
        decisions=(
            CandleCandidateDecision.SEGMENTED,
            CandleCandidateDecision.DIMENSION_ACCEPTED,
            CandleCandidateDecision.WIDTH_ACCEPTED,
            CandleCandidateDecision.RETURNED,
        ),
        dominant_width=8.0,
        width_decision_reason=CandleWidthDecisionReason.WITHIN_DOMINANT_RANGE,
    )


def test_candle_detection_trace_is_immutable_and_runtime_typed() -> None:
    trace = CandleDetectionTrace(
        candidates=(_candidate_trace(),),
        merges=(),
        returned_candidate_ids=("candidate_000",),
        dominant_width=8.0,
        maximum_returned_candidates=80,
    )

    assert (
        get_type_hints(CandleDetectionTrace)["candidates"]
        == (tuple[CandleCandidateTrace, ...])
    )
    with pytest.raises(FrozenInstanceError):
        trace.dominant_width = 10.0  # type: ignore[misc]


def test_merge_trace_requires_real_provenance() -> None:
    with pytest.raises(ValueError, match="al menos dos"):
        CandleMergeTrace(
            result_candidate_id="merged_000",
            source_candidate_ids=("candidate_000",),
            maximum_center_distance=2.0,
        )


def test_detection_trace_rejects_unknown_returned_candidate() -> None:
    with pytest.raises(ValueError, match="deben existir"):
        CandleDetectionTrace(
            candidates=(_candidate_trace(),),
            merges=(),
            returned_candidate_ids=("candidate_999",),
            dominant_width=8.0,
            maximum_returned_candidates=80,
        )
