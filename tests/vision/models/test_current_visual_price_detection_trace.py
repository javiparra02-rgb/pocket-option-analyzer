from dataclasses import FrozenInstanceError
from typing import get_type_hints

import pytest

from pocket_option_analyzer.vision.models import (
    CurrentVisualPriceAnalysis,
    CurrentVisualPriceCandidateTrace,
    CurrentVisualPriceDetectionTrace,
    CurrentVisualPriceExtraction,
    CurrentVisualPriceLabelSupportTrace,
    CurrentVisualPriceRejectionCounts,
    CurrentVisualPriceRowEvaluationTrace,
    CurrentVisualPriceRowRejectionReason,
    CurrentVisualPriceStatus,
)


def _candidate(*, selected: bool = True) -> CurrentVisualPriceCandidateTrace:
    return CurrentVisualPriceCandidateTrace(
        candidate_id="price_candidate_000",
        x=90.0,
        y=50.0,
        row_start=50,
        row_end=50,
        coverage=1.0,
        span=1.0,
        right_edge_gap=0,
        score=1.0,
        selected=selected,
    )


def _trace() -> CurrentVisualPriceDetectionTrace:
    return CurrentVisualPriceDetectionTrace(
        status=CurrentVisualPriceStatus.LOW_CONFIDENCE,
        image_width=100,
        image_height=100,
        effective_chart_right_x=100,
        effective_chart_right_source="image_width_fallback",
        band_start=80,
        band_end=100,
        band_width=20,
        safe_top=12,
        safe_bottom=12,
        masked_pixel_count=20,
        candidates=(_candidate(),),
        rejection_counts=CurrentVisualPriceRejectionCounts(
            rows_without_mask_pixels=99,
            rows_with_mask_pixels=1,
            qualifying_rows=1,
            candidate_groups=1,
        ),
    )


def _label_support() -> CurrentVisualPriceLabelSupportTrace:
    return CurrentVisualPriceLabelSupportTrace(
        window_start_y=47,
        window_end_y=54,
        zone_start_x=95,
        zone_end_x=100,
        support_pixels=20,
        support_row_count=4,
        evaluated_row_count=6,
        support_row_ratio=4 / 6,
        support_density=2 / 3,
        supported=True,
        diagnostic="label_support_available",
    )


def _row_evaluation() -> CurrentVisualPriceRowEvaluationTrace:
    return CurrentVisualPriceRowEvaluationTrace(
        row_y=50,
        masked_pixels=20,
        coverage=1.0,
        span=1.0,
        left_x=80,
        right_x=99,
        right_edge_gap=0,
        longest_run_pixels=20,
        longest_run_ratio=1.0,
        longest_run_start_x=80,
        longest_run_end_x=99,
        component_count=1,
        line_run_pixels=20,
        line_run_span_pixels=20,
        line_run_span_ratio=1.0,
        line_run_start_x=80,
        line_run_end_x=99,
        line_run_continuity=1.0,
        pass_coverage=True,
        pass_span=True,
        pass_edge=True,
        line_evidence=True,
        label_support=True,
        qualified=True,
        rejection_reasons=(),
        label_support_trace=_label_support(),
    )


def test_current_visual_price_trace_is_immutable_and_runtime_typed() -> None:
    trace = _trace()

    assert (
        get_type_hints(CurrentVisualPriceDetectionTrace)["candidates"]
        == (tuple[CurrentVisualPriceCandidateTrace, ...])
    )
    with pytest.raises(FrozenInstanceError):
        trace.masked_pixel_count = 2  # type: ignore[misc]


def test_row_and_label_traces_are_immutable_and_runtime_typed() -> None:
    row = _row_evaluation()

    assert (
        get_type_hints(CurrentVisualPriceRowEvaluationTrace)["rejection_reasons"]
        == tuple[CurrentVisualPriceRowRejectionReason, ...]
    )
    assert (
        get_type_hints(CurrentVisualPriceDetectionTrace)["row_evaluations"]
        == tuple[CurrentVisualPriceRowEvaluationTrace, ...]
    )
    assert (
        get_type_hints(CurrentVisualPriceRowEvaluationTrace)["label_support_trace"]
        == CurrentVisualPriceLabelSupportTrace | None
    )
    with pytest.raises(FrozenInstanceError):
        row.qualified = False  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        row.label_support_trace.supported = False  # type: ignore[union-attr,misc]


def test_row_trace_rejects_contradictory_qualification() -> None:
    values = {
        field: getattr(_row_evaluation(), field)
        for field in _row_evaluation().__dataclass_fields__
    }
    values["qualified"] = False
    values["rejection_reasons"] = (
        CurrentVisualPriceRowRejectionReason.LABEL_SUPPORT_MISSING,
    )

    with pytest.raises(ValueError, match="qualified"):
        CurrentVisualPriceRowEvaluationTrace(**values)


def test_trace_requires_one_selected_candidate_when_candidates_exist() -> None:
    with pytest.raises(ValueError, match="identificar el seleccionado"):
        CurrentVisualPriceDetectionTrace(
            status=CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE,
            image_width=100,
            image_height=100,
            effective_chart_right_x=100,
            effective_chart_right_source="image_width_fallback",
            band_start=80,
            band_end=100,
            band_width=20,
            safe_top=12,
            safe_bottom=12,
            masked_pixel_count=20,
            candidates=(_candidate(selected=False),),
            rejection_counts=CurrentVisualPriceRejectionCounts(),
        )


def test_analysis_rejects_extraction_trace_status_mismatch() -> None:
    extraction = CurrentVisualPriceExtraction(
        price=None,
        status=CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE,
    )

    with pytest.raises(ValueError, match="compartir status"):
        CurrentVisualPriceAnalysis(extraction=extraction, trace=_trace())
