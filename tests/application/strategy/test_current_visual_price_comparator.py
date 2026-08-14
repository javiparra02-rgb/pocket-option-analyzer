from dataclasses import FrozenInstanceError, replace

import pytest

from pocket_option_analyzer.application.strategy import (
    CurrentVisualPriceComparator,
    CurrentVisualPriceComparison,
    CurrentVisualPriceComparisonContext,
    CurrentVisualPriceComparisonDiagnostic,
    CurrentVisualPriceComparisonStatus,
    VisualPriceReference,
    VisualPriceReferenceResult,
    VisualPriceReferenceStatus,
)
from pocket_option_analyzer.vision.models import (
    ChartRegion,
    CurrentVisualPrice,
    CurrentVisualPriceExtraction,
    CurrentVisualPriceStatus,
)

_ANCHORS = (
    ("bullish", 1.0, 0.8, 0.6, 0.4),
    ("bearish", 0.7, 0.5, 0.3, 0.0),
)
_DEFAULT_CHART_REGION = ChartRegion(10, 100, 400, 400)
_DEFAULT_PRICE_REGION = ChartRegion(0, 0, 500, 500)


def _context(
    *,
    roi_y: float = 250.0,
    normalized_roi_y: float | None = None,
    chart_region: ChartRegion = _DEFAULT_CHART_REGION,
    price_region: ChartRegion = _DEFAULT_PRICE_REGION,
    source: str = "current_visual_price_roi_v1",
    candidate_count: int = 1,
    anchor_top: int | None = 100,
    anchor_bottom: int | None = 300,
    anchor_shape: tuple[tuple[str, float, float, float, float], ...] = _ANCHORS,
) -> CurrentVisualPriceComparisonContext:
    normalized = (
        normalized_roi_y
        if normalized_roi_y is not None
        else (price_region.height - 1 - roi_y) / (price_region.height - 1)
    )
    extraction = CurrentVisualPriceExtraction(
        price=CurrentVisualPrice(
            roi_y=roi_y,
            normalized_roi_y=normalized,
            roi_width=price_region.width,
            roi_height=price_region.height,
            source=source,
            confidence=0.91,
        ),
        status=CurrentVisualPriceStatus.OK,
        candidate_count=candidate_count,
        confidence=0.91,
    )
    reference_result = VisualPriceReferenceResult(
        reference=VisualPriceReference(0.5, anchor_shape=anchor_shape),
        status=VisualPriceReferenceStatus.OK,
        anchor_top_roi_y=anchor_top,
        anchor_bottom_roi_y=anchor_bottom,
    )
    return CurrentVisualPriceComparisonContext(
        current_visual_price=extraction,
        chart_region=chart_region,
        price_observation_region=price_region,
        reference_result=reference_result,
    )


def _compare(
    entry: CurrentVisualPriceComparisonContext | None,
    exit: CurrentVisualPriceComparisonContext | None,
):
    return CurrentVisualPriceComparator().compare(entry, exit)


def test_comparator_produces_positive_delta() -> None:
    comparison = _compare(_context(), _context(roi_y=200.0))

    assert comparison.status is CurrentVisualPriceComparisonStatus.AVAILABLE
    assert (
        comparison.diagnostic
        is CurrentVisualPriceComparisonDiagnostic.COMPARISON_AVAILABLE
    )
    assert comparison.entry_anchored_value == pytest.approx(0.75)
    assert comparison.exit_anchored_value == pytest.approx(1.0)
    assert comparison.delta == pytest.approx(0.25)


def test_comparison_result_is_immutable() -> None:
    comparison = _compare(_context(), _context())

    with pytest.raises(FrozenInstanceError):
        comparison.delta = 1.0  # type: ignore[misc]


def test_available_comparison_requires_all_numeric_evidence() -> None:
    with pytest.raises(ValueError, match="todas las coordenadas"):
        CurrentVisualPriceComparison(
            status=CurrentVisualPriceComparisonStatus.AVAILABLE,
            diagnostic=(
                CurrentVisualPriceComparisonDiagnostic.COMPARISON_AVAILABLE
            ),
        )


def test_available_comparison_requires_available_diagnostic() -> None:
    with pytest.raises(ValueError, match="AVAILABLE requiere"):
        CurrentVisualPriceComparison(
            status=CurrentVisualPriceComparisonStatus.AVAILABLE,
            diagnostic=(
                CurrentVisualPriceComparisonDiagnostic.ENTRY_CONTEXT_MISSING
            ),
            entry_anchored_value=0.5,
            exit_anchored_value=0.5,
            delta=0.0,
            entry_price_y_in_chart_roi=100.0,
            exit_price_y_in_chart_roi=100.0,
        )


def test_unavailable_comparison_rejects_available_diagnostic() -> None:
    with pytest.raises(ValueError, match="UNAVAILABLE no admite"):
        CurrentVisualPriceComparison(
            status=CurrentVisualPriceComparisonStatus.UNAVAILABLE,
            diagnostic=(
                CurrentVisualPriceComparisonDiagnostic.COMPARISON_AVAILABLE
            ),
        )


def test_unavailable_comparison_rejects_delta() -> None:
    with pytest.raises(ValueError, match="delta=None"):
        CurrentVisualPriceComparison(
            status=CurrentVisualPriceComparisonStatus.UNAVAILABLE,
            diagnostic=(
                CurrentVisualPriceComparisonDiagnostic.EXIT_CONTEXT_MISSING
            ),
            delta=0.1,
        )


@pytest.mark.parametrize(
    "partial_evidence",
    (
        {"entry_price_y_in_chart_roi": 100.0},
        {"entry_anchored_value": 0.5},
        {"exit_price_y_in_chart_roi": 100.0},
        {"exit_anchored_value": 0.5},
    ),
)
def test_unavailable_comparison_rejects_incoherent_side_evidence(
    partial_evidence: dict[str, float],
) -> None:
    with pytest.raises(ValueError, match="coherentes"):
        CurrentVisualPriceComparison(
            status=CurrentVisualPriceComparisonStatus.UNAVAILABLE,
            diagnostic=(
                CurrentVisualPriceComparisonDiagnostic.SOURCES_NOT_COMPARABLE
            ),
            **partial_evidence,
        )


def test_unavailable_comparison_accepts_coherent_partial_entry_evidence() -> None:
    comparison = CurrentVisualPriceComparison(
        status=CurrentVisualPriceComparisonStatus.UNAVAILABLE,
        diagnostic=(
            CurrentVisualPriceComparisonDiagnostic.EXIT_EXTRACTION_UNAVAILABLE
        ),
        entry_anchored_value=0.5,
        entry_price_y_in_chart_roi=100.0,
    )

    assert comparison.entry_anchored_value == 0.5
    assert comparison.entry_price_y_in_chart_roi == 100.0
    assert comparison.exit_anchored_value is None
    assert comparison.exit_price_y_in_chart_roi is None


def test_comparator_produces_negative_delta() -> None:
    comparison = _compare(_context(), _context(roi_y=300.0))

    assert comparison.status is CurrentVisualPriceComparisonStatus.AVAILABLE
    assert comparison.delta == pytest.approx(-0.25)


def test_comparator_produces_exact_zero_delta() -> None:
    comparison = _compare(_context(), _context())

    assert comparison.status is CurrentVisualPriceComparisonStatus.AVAILABLE
    assert comparison.delta == 0.0


def test_comparator_reports_missing_entry_context() -> None:
    comparison = _compare(None, _context())

    assert comparison.status is CurrentVisualPriceComparisonStatus.UNAVAILABLE
    assert (
        comparison.diagnostic
        is CurrentVisualPriceComparisonDiagnostic.ENTRY_CONTEXT_MISSING
    )


def test_comparator_reports_missing_exit_context() -> None:
    comparison = _compare(_context(), None)

    assert (
        comparison.diagnostic
        is CurrentVisualPriceComparisonDiagnostic.EXIT_CONTEXT_MISSING
    )
    assert comparison.delta is None


@pytest.mark.parametrize("side", ("entry", "exit"))
def test_comparator_rejects_unavailable_extraction(side: str) -> None:
    unavailable = replace(
        _context(),
        current_visual_price=CurrentVisualPriceExtraction(
            price=None,
            status=CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE,
        ),
    )
    entry, exit = (
        (unavailable, _context())
        if side == "entry"
        else (_context(), unavailable)
    )

    comparison = _compare(entry, exit)

    assert comparison.diagnostic.value == f"{side}_extraction_unavailable"


def test_comparator_rejects_price_none_even_with_ok_status() -> None:
    invalid = replace(
        _context(),
        current_visual_price=CurrentVisualPriceExtraction(
            price=None,
            status=CurrentVisualPriceStatus.OK,
        ),
    )

    comparison = _compare(invalid, _context())

    assert (
        comparison.diagnostic
        is CurrentVisualPriceComparisonDiagnostic.ENTRY_EXTRACTION_UNAVAILABLE
    )


@pytest.mark.parametrize("side", ("entry", "exit"))
def test_comparator_reports_missing_geometry(side: str) -> None:
    missing = replace(_context(), chart_region=None)
    entry, exit = (missing, _context()) if side == "entry" else (_context(), missing)

    comparison = _compare(entry, exit)

    assert comparison.diagnostic.value == f"{side}_geometry_missing"


def test_comparator_rejects_extraction_dimensions_incompatible_with_roi() -> None:
    context = _context()
    extraction = context.current_visual_price
    assert extraction is not None and extraction.price is not None
    invalid = replace(
        context,
        current_visual_price=replace(
            extraction,
            price=replace(extraction.price, roi_width=499),
        ),
    )

    comparison = _compare(invalid, _context())

    assert (
        comparison.diagnostic
        is CurrentVisualPriceComparisonDiagnostic.ENTRY_GEOMETRY_INCOHERENT
    )


def test_comparator_rejects_price_mapping_outside_chart_space() -> None:
    comparison = _compare(_context(roi_y=50.0), _context())

    assert (
        comparison.diagnostic
        is CurrentVisualPriceComparisonDiagnostic.ENTRY_GEOMETRY_INCOHERENT
    )


def test_comparator_rejects_different_extraction_sources() -> None:
    comparison = _compare(_context(), _context(source="other_roi_system"))

    assert (
        comparison.diagnostic
        is CurrentVisualPriceComparisonDiagnostic.SOURCES_NOT_COMPARABLE
    )
    assert comparison.entry_anchored_value == pytest.approx(0.75)
    assert comparison.exit_anchored_value == pytest.approx(0.75)
    assert comparison.delta is None


def test_comparator_rejects_unavailable_reference() -> None:
    context = _context()
    invalid = replace(
        context,
        reference_result=replace(
            context.reference_result,
            reference=None,
            status=VisualPriceReferenceStatus.LATEST_CANDLE_MISSING,
        ),
    )

    comparison = _compare(invalid, _context())

    assert (
        comparison.diagnostic
        is CurrentVisualPriceComparisonDiagnostic.ENTRY_REFERENCE_UNAVAILABLE
    )


def test_comparator_rejects_missing_anchors() -> None:
    comparison = _compare(_context(anchor_top=None), _context())

    assert (
        comparison.diagnostic
        is CurrentVisualPriceComparisonDiagnostic.ENTRY_ANCHORS_MISSING
    )


def test_comparator_rejects_degenerate_anchors() -> None:
    comparison = _compare(
        _context(anchor_top=200, anchor_bottom=200),
        _context(),
    )

    assert (
        comparison.diagnostic
        is CurrentVisualPriceComparisonDiagnostic.ENTRY_ANCHORS_DEGENERATE
    )


def test_comparator_rejects_anchors_outside_chart_space() -> None:
    comparison = _compare(_context(anchor_bottom=400), _context())

    assert (
        comparison.diagnostic
        is CurrentVisualPriceComparisonDiagnostic.ENTRY_ANCHORS_INCOHERENT
    )


def test_comparator_reuses_legacy_reference_comparability() -> None:
    incompatible_shape = (
        ("bullish", 1.0, 0.8, 0.6, 0.4),
        ("bearish", 0.7, 0.5, 0.3, 0.03),
    )

    comparison = _compare(_context(), _context(anchor_shape=incompatible_shape))

    assert (
        comparison.diagnostic
        is CurrentVisualPriceComparisonDiagnostic.REFERENCES_NOT_COMPARABLE
    )


def test_comparator_accepts_different_frame_geometries() -> None:
    entry = _context()
    exit = _context(
        roi_y=475.0,
        chart_region=ChartRegion(40, 300, 600, 500),
        price_region=ChartRegion(5, 0, 700, 800),
        anchor_top=100,
        anchor_bottom=350,
    )

    comparison = _compare(entry, exit)

    assert comparison.status is CurrentVisualPriceComparisonStatus.AVAILABLE
    assert comparison.entry_price_y_in_chart_roi == pytest.approx(150.0)
    assert comparison.exit_price_y_in_chart_roi == pytest.approx(175.0)
    assert comparison.delta == pytest.approx(-0.05)


def test_different_geometries_can_produce_same_canonical_value() -> None:
    entry = _context()
    exit = _context(
        roi_y=475.0,
        chart_region=ChartRegion(40, 300, 600, 500),
        price_region=ChartRegion(5, 0, 700, 800),
        anchor_top=100,
        anchor_bottom=400,
    )
    entry_extraction = entry.current_visual_price
    exit_extraction = exit.current_visual_price
    assert entry_extraction is not None and entry_extraction.price is not None
    assert exit_extraction is not None and exit_extraction.price is not None

    comparison = _compare(entry, exit)

    assert (
        entry_extraction.price.normalized_roi_y
        != exit_extraction.price.normalized_roi_y
    )
    assert comparison.entry_anchored_value == pytest.approx(0.75)
    assert comparison.exit_anchored_value == pytest.approx(0.75)
    assert comparison.delta == 0.0


def test_comparator_respects_origins_for_equal_sized_regions() -> None:
    entry = _context()
    exit = _context(
        chart_region=ChartRegion(10, 100, 400, 400),
        price_region=ChartRegion(0, 100, 500, 500),
    )

    comparison = _compare(entry, exit)

    assert comparison.status is CurrentVisualPriceComparisonStatus.AVAILABLE
    assert comparison.entry_price_y_in_chart_roi == pytest.approx(150.0)
    assert comparison.exit_price_y_in_chart_roi == pytest.approx(250.0)
    assert comparison.delta == pytest.approx(-0.5)


def test_comparator_does_not_compare_normalized_roi_y_directly() -> None:
    entry = _context(
        roi_y=200.0,
        chart_region=ChartRegion(10, 100, 400, 400),
        price_region=ChartRegion(0, 100, 500, 500),
        anchor_top=100,
        anchor_bottom=300,
    )
    exit = _context(
        roi_y=450.0,
        chart_region=ChartRegion(10, 300, 400, 400),
        price_region=ChartRegion(0, 0, 700, 800),
        anchor_top=100,
        anchor_bottom=300,
    )
    entry_price = entry.current_visual_price
    exit_price = exit.current_visual_price
    assert entry_price is not None and entry_price.price is not None
    assert exit_price is not None and exit_price.price is not None
    direct_normalized_delta = (
        exit_price.price.normalized_roi_y
        - entry_price.price.normalized_roi_y
    )

    comparison = _compare(entry, exit)

    assert direct_normalized_delta < 0.0
    assert comparison.delta == pytest.approx(0.25)


@pytest.mark.parametrize(
    ("roi_y", "expected"),
    ((175.0, 1.125), (425.0, -0.125)),
)
def test_comparator_preserves_anchored_values_outside_unit_interval(
    roi_y: float,
    expected: float,
) -> None:
    comparison = _compare(_context(roi_y=roi_y), _context(roi_y=roi_y))

    assert comparison.status is CurrentVisualPriceComparisonStatus.AVAILABLE
    assert comparison.entry_anchored_value == pytest.approx(expected)
    assert comparison.exit_anchored_value == pytest.approx(expected)


def test_comparator_accepts_valid_extraction_with_multiple_candidates() -> None:
    comparison = _compare(
        _context(candidate_count=4),
        _context(candidate_count=3),
    )

    assert comparison.status is CurrentVisualPriceComparisonStatus.AVAILABLE
    assert comparison.delta == 0.0


@pytest.mark.parametrize("roi_y", (0.0, 499.0))
def test_comparator_accepts_exact_price_roi_edges(roi_y: float) -> None:
    context = _context(
        roi_y=roi_y,
        chart_region=ChartRegion(0, 0, 400, 500),
        price_region=ChartRegion(0, 0, 500, 500),
    )

    comparison = _compare(context, context)

    assert comparison.status is CurrentVisualPriceComparisonStatus.AVAILABLE
    assert comparison.entry_price_y_in_chart_roi == roi_y
    assert comparison.delta == 0.0


@pytest.mark.parametrize("roi_y", (-1.0, 500.0))
def test_current_visual_price_rejects_coordinates_outside_roi(roi_y: float) -> None:
    with pytest.raises(ValueError, match="roi_y"):
        _context(
            roi_y=roi_y,
            chart_region=ChartRegion(0, 0, 400, 500),
            price_region=ChartRegion(0, 0, 500, 500),
        )
