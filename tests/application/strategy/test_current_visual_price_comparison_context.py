from dataclasses import FrozenInstanceError, fields
from typing import get_type_hints

import pytest

from pocket_option_analyzer.application.signals import (
    VisualStrategySignalAnalysisPipeline,
)
from pocket_option_analyzer.application.strategy import (
    CurrentVisualPriceComparator,
    CurrentVisualPriceComparison,
    CurrentVisualPriceComparisonContext,
    StrategyObservation,
    StrategyObservationOutcomeResolver,
    StrategyObservationRecorder,
    StrategyObservationResolution,
    VisualPriceReference,
    VisualPriceReferenceResult,
    VisualPriceReferenceStatus,
    VisualReferenceResolution,
    VisualReferenceValidation,
    VisualReferenceValidationResolver,
)
from pocket_option_analyzer.vision.models import (
    ChartRegion,
    CurrentVisualPrice,
    CurrentVisualPriceExtraction,
    CurrentVisualPriceStatus,
)


def _reference_result() -> VisualPriceReferenceResult:
    return VisualPriceReferenceResult(
        reference=VisualPriceReference(value=0.5),
        status=VisualPriceReferenceStatus.OK,
        anchor_top_roi_y=100,
        anchor_bottom_roi_y=700,
    )


def test_context_preserves_same_frame_evidence_by_identity() -> None:
    extraction = CurrentVisualPriceExtraction(
        price=CurrentVisualPrice(514.0, 0.73125, 1320, 800, "test", 0.92),
        status=CurrentVisualPriceStatus.OK,
    )
    chart_region = ChartRegion(x=20, y=30, width=1000, height=700)
    price_region = ChartRegion(x=0, y=80, width=1320, height=800)
    reference_result = _reference_result()

    context = CurrentVisualPriceComparisonContext(
        current_visual_price=extraction,
        chart_region=chart_region,
        price_observation_region=price_region,
        reference_result=reference_result,
    )

    assert context.current_visual_price is extraction
    assert context.chart_region is chart_region
    assert context.price_observation_region is price_region
    assert context.reference_result is reference_result


def test_context_accepts_missing_price_and_legacy_geometry() -> None:
    context = CurrentVisualPriceComparisonContext(
        current_visual_price=None,
        chart_region=None,
        price_observation_region=None,
        reference_result=_reference_result(),
    )

    assert context.current_visual_price is None
    assert context.chart_region is None
    assert context.price_observation_region is None


def test_context_is_immutable_and_contains_no_comparison_result() -> None:
    context = CurrentVisualPriceComparisonContext(
        current_visual_price=None,
        chart_region=None,
        price_observation_region=None,
        reference_result=_reference_result(),
    )

    assert {field.name for field in fields(context)} == {
        "current_visual_price",
        "chart_region",
        "price_observation_region",
        "reference_result",
    }
    with pytest.raises(FrozenInstanceError):
        context.chart_region = None  # type: ignore[misc]


@pytest.mark.parametrize(
    "target",
    (
        CurrentVisualPriceComparisonContext,
        CurrentVisualPriceComparison,
        CurrentVisualPriceComparator.compare,
        StrategyObservation,
        StrategyObservationResolution,
        VisualReferenceValidation,
        VisualReferenceResolution,
        StrategyObservationOutcomeResolver.resolve_due,
        StrategyObservationRecorder.resolve_due,
        VisualReferenceValidationResolver.resolve_due,
        VisualStrategySignalAnalysisPipeline.analyze,
        VisualStrategySignalAnalysisPipeline.last_visual_price_comparison_context.fget,
    ),
)
def test_p03b_public_type_hints_are_runtime_resolvable(target: object) -> None:
    assert get_type_hints(target)
