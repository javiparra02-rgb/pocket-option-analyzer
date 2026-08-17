from dataclasses import FrozenInstanceError
from typing import get_type_hints

import pytest

from pocket_option_analyzer.vision.models import (
    CurrentVisualPriceAnalysis,
    CurrentVisualPriceCandidateTrace,
    CurrentVisualPriceDetectionTrace,
    CurrentVisualPriceExtraction,
    CurrentVisualPriceRejectionCounts,
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


def test_current_visual_price_trace_is_immutable_and_runtime_typed() -> None:
    trace = _trace()

    assert (
        get_type_hints(CurrentVisualPriceDetectionTrace)["candidates"]
        == (tuple[CurrentVisualPriceCandidateTrace, ...])
    )
    with pytest.raises(FrozenInstanceError):
        trace.masked_pixel_count = 2  # type: ignore[misc]


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
