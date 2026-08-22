from __future__ import annotations

import numpy as np
import pytest

from pocket_option_analyzer.vision.models import (
    CurrentVisualPriceRowRejectionReason,
    CurrentVisualPriceStatus,
)
from pocket_option_analyzer.vision.services import (
    PocketOptionCurrentVisualPriceExtractor,
)


class _FixedMaskBuilder:
    def __init__(self, mask: np.ndarray) -> None:
        self._mask = mask

    def build(self, frame: np.ndarray) -> np.ndarray:
        assert frame.shape[:2] == self._mask.shape
        return self._mask.copy()


def _analyze(
    mask: np.ndarray,
    *,
    effective_chart_right_x: int | None = None,
    **configuration: object,
):
    image = np.zeros((*mask.shape, 3), dtype=np.uint8)
    extractor = PocketOptionCurrentVisualPriceExtractor(
        mask_builder=_FixedMaskBuilder(mask),
        effective_chart_right_x=effective_chart_right_x,
        **configuration,  # type: ignore[arg-type]
    )
    return extractor.extract_with_trace(image)


def _add_marker(
    mask: np.ndarray,
    *,
    y: int,
    band_start: int,
    line_end: int,
    label_start: int,
    label_end: int,
    label_radius: int = 3,
) -> None:
    mask[y, band_start : line_end + 1] = 255
    mask[y - label_radius : y, label_start : label_end + 1] = 255
    mask[y + 1 : y + label_radius + 1, label_start : label_end + 1] = 255


def test_long_horizontal_line_without_label_is_rejected() -> None:
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[50, 80:100] = 255

    analysis = _analyze(mask)

    assert analysis.extraction.status is (
        CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE
    )
    row = analysis.trace.row_evaluations[0]
    assert row.line_evidence is True
    assert row.label_support is False
    assert row.rejection_reasons == (
        CurrentVisualPriceRowRejectionReason.LABEL_SUPPORT_MISSING,
    )
    assert analysis.trace.decision_diagnostic == "line_rows_without_label_support"


def test_label_without_horizontal_line_is_rejected() -> None:
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[47:54, 95:100] = 255

    analysis = _analyze(mask)

    assert analysis.extraction.status is (
        CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE
    )
    assert not any(row.line_evidence for row in analysis.trace.row_evaluations)
    assert analysis.trace.decision_diagnostic == "no_line_rows"


def test_multiple_isolated_grid_lines_are_rejected() -> None:
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[[30, 50, 70], 80:100] = 255

    analysis = _analyze(mask)

    assert analysis.extraction.status is (
        CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE
    )
    assert analysis.trace.rejection_counts.line_evidence_rows == 3
    assert analysis.trace.rejection_counts.rejected_by_label_support == 3


def test_short_fragment_and_disperse_large_span_are_rejected() -> None:
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[30, 96:100] = 255
    mask[60, [80, 85, 90, 95, 99]] = 255

    analysis = _analyze(mask)

    assert analysis.extraction.status is (
        CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE
    )
    by_y = {row.row_y: row for row in analysis.trace.row_evaluations}
    assert by_y[60].span == 1.0
    assert by_y[60].longest_run_pixels == 1
    assert by_y[60].line_evidence is False


@pytest.mark.parametrize("same_row_gap", [0, 5, 7, 10])
def test_marker_does_not_depend_on_terminal_same_row_gap(
    same_row_gap: int,
) -> None:
    mask = np.zeros((100, 500), dtype=np.uint8)
    _add_marker(
        mask,
        y=50,
        band_start=400,
        line_end=479,
        label_start=475,
        label_end=499,
    )
    mask[50, 499 - same_row_gap] = 255

    analysis = _analyze(mask)

    assert analysis.extraction.status is CurrentVisualPriceStatus.OK
    row = next(row for row in analysis.trace.row_evaluations if row.qualified)
    assert row.right_edge_gap == same_row_gap
    assert row.line_evidence is True
    assert row.label_support is True


def test_small_internal_line_gap_is_tolerated_and_traced() -> None:
    mask = np.zeros((100, 100), dtype=np.uint8)
    _add_marker(
        mask,
        y=50,
        band_start=80,
        line_end=94,
        label_start=95,
        label_end=99,
    )
    mask[50, 80:100] = 255
    mask[50, 87] = 0

    analysis = _analyze(mask)

    assert analysis.extraction.status is CurrentVisualPriceStatus.OK
    row = next(row for row in analysis.trace.row_evaluations if row.qualified)
    assert row.component_count == 2
    assert row.longest_run_pixels < row.line_run_span_pixels
    assert row.line_run_continuity == pytest.approx(19 / 20)


@pytest.mark.parametrize("label_columns", [(95, 97, 99), (96, 97, 98, 99)])
def test_sparse_label_patterns_support_different_glyph_geometry(
    label_columns: tuple[int, ...],
) -> None:
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[50, 80:95] = 255
    for y in (47, 49, 51, 53):
        mask[y, label_columns] = 255

    analysis = _analyze(mask)

    assert analysis.extraction.status is CurrentVisualPriceStatus.OK
    row = next(row for row in analysis.trace.row_evaluations if row.qualified)
    assert row.label_support_trace is not None
    assert row.label_support_trace.support_row_count == 4
    assert row.label_support_trace.diagnostic == "label_support_available"


@pytest.mark.parametrize("width", [1168, 1170])
def test_marker_is_invariant_to_observed_roi_widths(width: int) -> None:
    mask = np.zeros((100, width), dtype=np.uint8)
    _add_marker(
        mask,
        y=50,
        band_start=849,
        line_end=1021,
        label_start=1008,
        label_end=1061,
    )

    analysis = _analyze(mask, effective_chart_right_x=1062)

    assert analysis.extraction.status is CurrentVisualPriceStatus.OK
    assert analysis.extraction.selected_y == 50.0
    assert analysis.trace.band_start == 849
    assert analysis.trace.band_end == 1062


def test_pixels_in_side_panel_cannot_supply_label_support() -> None:
    mask = np.zeros((100, 1170), dtype=np.uint8)
    mask[50, 849:1022] = 255
    mask[47:54, 1062:1170] = 255

    analysis = _analyze(mask, effective_chart_right_x=1062)

    assert analysis.extraction.status is (
        CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE
    )
    assert analysis.trace.decision_diagnostic == "line_rows_without_label_support"


def test_two_supported_marker_lines_remain_ambiguous() -> None:
    mask = np.zeros((100, 100), dtype=np.uint8)
    for y in (35, 65):
        _add_marker(
            mask,
            y=y,
            band_start=80,
            line_end=94,
            label_start=95,
            label_end=99,
        )

    analysis = _analyze(mask)

    assert analysis.extraction.status is (
        CurrentVisualPriceStatus.AMBIGUOUS_VISUAL_PRICE
    )
    assert analysis.trace.decision_diagnostic == "ambiguous_candidates"
    assert len(analysis.trace.candidates) == 2


def test_line_ratio_boundary_is_explicit() -> None:
    accepted = np.zeros((100, 100), dtype=np.uint8)
    _add_marker(
        accepted,
        y=50,
        band_start=80,
        line_end=93,
        label_start=95,
        label_end=99,
    )
    rejected = accepted.copy()
    rejected[50, 93] = 0

    accepted_analysis = _analyze(accepted)
    rejected_analysis = _analyze(rejected)

    assert accepted_analysis.extraction.status is CurrentVisualPriceStatus.OK
    assert rejected_analysis.extraction.status is (
        CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE
    )


def test_line_continuity_boundary_is_explicit() -> None:
    accepted = np.zeros((100, 100), dtype=np.uint8)
    _add_marker(
        accepted,
        y=50,
        band_start=80,
        line_end=99,
        label_start=95,
        label_end=99,
    )
    accepted[50, [85, 90]] = 0
    rejected = accepted.copy()
    rejected[50, 87] = 0

    accepted_analysis = _analyze(accepted)
    rejected_analysis = _analyze(rejected)

    assert accepted_analysis.extraction.status is CurrentVisualPriceStatus.OK
    assert rejected_analysis.extraction.status is (
        CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE
    )


def test_line_start_offset_boundary_is_explicit() -> None:
    accepted = np.zeros((100, 100), dtype=np.uint8)
    _add_marker(
        accepted,
        y=50,
        band_start=81,
        line_end=94,
        label_start=95,
        label_end=99,
    )
    rejected = accepted.copy()
    rejected[50, 81] = 0

    accepted_analysis = _analyze(accepted)
    rejected_analysis = _analyze(rejected)

    assert accepted_analysis.extraction.status is CurrentVisualPriceStatus.OK
    assert rejected_analysis.extraction.status is (
        CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE
    )


def test_two_pixel_internal_gap_exceeds_default_merge_boundary() -> None:
    mask = np.zeros((100, 100), dtype=np.uint8)
    _add_marker(
        mask,
        y=50,
        band_start=80,
        line_end=94,
        label_start=95,
        label_end=99,
    )
    mask[50, 87:89] = 0

    analysis = _analyze(mask)

    assert analysis.extraction.status is (
        CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE
    )


def test_label_support_must_be_inside_configured_right_zone() -> None:
    inside = np.zeros((100, 100), dtype=np.uint8)
    inside[50, 80:95] = 255
    inside[47:54, 95:100] = 255
    outside = np.zeros((100, 100), dtype=np.uint8)
    outside[50, 80:95] = 255
    outside[47:54, 90:95] = 255

    assert _analyze(inside).extraction.status is CurrentVisualPriceStatus.OK
    assert _analyze(outside).extraction.status is (
        CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE
    )


def test_label_vertical_radius_boundary_is_explicit() -> None:
    inside = np.zeros((100, 100), dtype=np.uint8)
    inside[50, 80:95] = 255
    inside[[47, 53], 95:100] = 255
    outside = np.zeros((100, 100), dtype=np.uint8)
    outside[50, 80:95] = 255
    outside[[46, 54], 95:100] = 255

    assert _analyze(inside).extraction.status is CurrentVisualPriceStatus.OK
    assert _analyze(outside).extraction.status is (
        CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE
    )


def test_label_support_row_ratio_requires_two_of_six_evaluated_rows() -> None:
    accepted = np.zeros((100, 100), dtype=np.uint8)
    accepted[50, 80:95] = 255
    accepted[[49, 51], 95:100] = 255
    rejected = np.zeros((100, 100), dtype=np.uint8)
    rejected[50, 80:95] = 255
    rejected[49, 95:100] = 255

    assert _analyze(accepted).extraction.status is CurrentVisualPriceStatus.OK
    assert _analyze(rejected).extraction.status is (
        CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE
    )


def test_label_support_density_boundary_is_explicit() -> None:
    accepted = np.zeros((100, 100), dtype=np.uint8)
    accepted[50, 80:95] = 255
    accepted[49, [98, 99]] = 255
    rejected = np.zeros((100, 100), dtype=np.uint8)
    rejected[50, 80:95] = 255
    rejected[49, 99] = 255

    configuration = {"min_label_support_row_ratio": 0.0}
    assert _analyze(accepted, **configuration).extraction.status is (
        CurrentVisualPriceStatus.OK
    )
    assert _analyze(rejected, **configuration).extraction.status is (
        CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE
    )


def test_empty_band_does_not_serialize_empty_row_objects() -> None:
    analysis = _analyze(np.zeros((100, 100), dtype=np.uint8))

    assert analysis.trace.row_evaluations == ()
    assert analysis.trace.rejection_counts.rows_without_mask_pixels == 100
    assert analysis.trace.decision_diagnostic == "no_pixels_in_band"
