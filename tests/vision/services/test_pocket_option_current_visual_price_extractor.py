from __future__ import annotations

from math import ceil

import cv2
import numpy as np
import pytest

from pocket_option_analyzer.vision.models import CurrentVisualPriceStatus
from pocket_option_analyzer.vision.services import (
    CurrentVisualPriceExtractor,
    PocketOptionCurrentPriceMaskBuilder,
    PocketOptionCurrentVisualPriceExtractor,
)

CURRENT_PRICE_BLUE = (126, 95, 79)


def image(height: int = 100, width: int = 100, channels: int = 3) -> np.ndarray:
    return np.zeros((height, width, channels), dtype=np.uint8)


def line(
    frame: np.ndarray,
    y: int,
    start: int = 80,
    end: int | None = None,
    color: tuple[int, ...] = CURRENT_PRICE_BLUE,
) -> None:
    line_end = frame.shape[1] - 1 if end is None else end
    cv2.line(frame, (start, y), (line_end, y), color, 1)


def marker(
    frame: np.ndarray,
    y: int,
    *,
    effective_right: int | None = None,
    right_gap: int = 0,
    color: tuple[int, ...] = CURRENT_PRICE_BLUE,
) -> None:
    """Dibuja línea primaria y soporte de etiqueta sin simular OCR."""

    chart_right = frame.shape[1] if effective_right is None else effective_right
    band_width = ceil(chart_right * 0.20)
    band_start = chart_right - band_width
    label_width = ceil(band_width * 0.25)
    label_right = chart_right - 1 - right_gap
    label_left = label_right - label_width + 1
    label_radius = max(1, ceil(frame.shape[0] * 0.025))
    cv2.rectangle(
        frame,
        (label_left, y - label_radius),
        (label_right, y + label_radius),
        color,
        -1,
    )
    cv2.line(frame, (band_start, y), (label_left, y), color, 1)


def test_implements_runtime_protocol() -> None:
    assert isinstance(
        PocketOptionCurrentVisualPriceExtractor(), CurrentVisualPriceExtractor
    )


def test_uses_current_price_mask_builder_by_default() -> None:
    extractor = PocketOptionCurrentVisualPriceExtractor()

    assert isinstance(extractor._mask_builder, PocketOptionCurrentPriceMaskBuilder)


@pytest.mark.parametrize(
    "invalid",
    [
        None,
        np.zeros((10, 10), dtype=np.uint8),
        np.zeros((10, 10, 3), dtype=np.float32),
        np.zeros((0, 10, 3), dtype=np.uint8),
    ],
)
def test_invalid_images(invalid: object) -> None:
    result = PocketOptionCurrentVisualPriceExtractor().extract(invalid)  # type: ignore[arg-type]
    assert result.status is CurrentVisualPriceStatus.INVALID_IMAGE


@pytest.mark.parametrize("channels", [3, 4])
def test_accepts_bgr_and_bgra(channels: int) -> None:
    frame = image(channels=channels)
    color = (*CURRENT_PRICE_BLUE, 255) if channels == 4 else CURRENT_PRICE_BLUE
    marker(frame, 50, color=color)
    assert (
        PocketOptionCurrentVisualPriceExtractor().extract(frame).status
        is CurrentVisualPriceStatus.OK
    )


def test_dark_roi_has_no_candidate() -> None:
    result = PocketOptionCurrentVisualPriceExtractor().extract(image())
    assert result.status is CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE


def test_effective_chart_right_detects_blue_line_before_side_panel() -> None:
    frame = image(height=800, width=1161)
    marker(frame, 400, effective_right=1062)

    result = PocketOptionCurrentVisualPriceExtractor(
        effective_chart_right_x=1062
    ).extract(frame)

    assert result.status is CurrentVisualPriceStatus.OK
    assert result.price is not None
    assert result.selected_x == 955.0


def test_image_width_fallback_does_not_treat_side_panel_as_chart() -> None:
    frame = image(height=800, width=1161)
    marker(frame, 400, effective_right=1062)

    result = PocketOptionCurrentVisualPriceExtractor().extract(frame)

    assert result.status is CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE
    assert result.diagnostic is not None
    assert "effective_chart_right_source=image_width_fallback" in result.diagnostic


def test_effective_chart_band_geometry_is_exact() -> None:
    frame = image(height=800, width=1161)
    marker(frame, 400, effective_right=1062)

    result = PocketOptionCurrentVisualPriceExtractor(
        effective_chart_right_x=1062
    ).extract(frame)

    assert result.diagnostic is not None
    assert "band_start=849; band_end=1062; band_width=213" in result.diagnostic


def test_right_edge_gap_uses_effective_chart_edge() -> None:
    frame = image(height=800, width=1161)
    marker(frame, 400, effective_right=1062, right_gap=2)

    result = PocketOptionCurrentVisualPriceExtractor(
        effective_chart_right_x=1062
    ).extract(frame)

    assert result.status is CurrentVisualPriceStatus.OK
    assert result.diagnostic is not None
    assert "right_edge_gap=2" in result.diagnostic


def test_diagnostic_contains_effective_edge_and_mask_fields() -> None:
    frame = image(height=800, width=1161)
    marker(frame, 400, effective_right=1062)

    result = PocketOptionCurrentVisualPriceExtractor(
        effective_chart_right_x=1062
    ).extract(frame)

    assert result.diagnostic is not None
    for field in (
        "image_width=1161",
        "effective_chart_right_x=1062",
        "effective_chart_right_source=configured",
        "band_start=849",
        "band_end=1062",
        "band_width=213",
        "masked_pixel_count=",
    ):
        assert field in result.diagnostic


@pytest.mark.parametrize("effective_chart_right_x", [0, -1, 1.5, True])
def test_invalid_effective_chart_right_x_configuration(
    effective_chart_right_x: object,
) -> None:
    with pytest.raises(ValueError):
        PocketOptionCurrentVisualPriceExtractor(
            effective_chart_right_x=effective_chart_right_x  # type: ignore[arg-type]
        )


def test_effective_chart_right_x_cannot_exceed_image_width() -> None:
    extractor = PocketOptionCurrentVisualPriceExtractor(effective_chart_right_x=101)

    with pytest.raises(ValueError):
        extractor.extract(image(width=100))


@pytest.mark.parametrize("color", [(255, 255, 255), (0, 0, 255)])
def test_white_and_red_lines_are_rejected(color: tuple[int, ...]) -> None:
    frame = image()
    line(frame, 50, color=color)
    result = PocketOptionCurrentVisualPriceExtractor().extract(frame)
    assert result.status is CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE


def test_line_outside_right_band_is_rejected() -> None:
    frame = image()
    cv2.line(frame, (10, 50), (70, 50), CURRENT_PRICE_BLUE, 1)
    assert (
        PocketOptionCurrentVisualPriceExtractor().extract(frame).status
        is CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE
    )


@pytest.mark.parametrize("y", [1, 11, 12, 50, 87, 88, 98])
def test_trusted_marker_availability_does_not_depend_on_safe_margin(y: int) -> None:
    frame = image()
    marker(frame, y)

    analysis = PocketOptionCurrentVisualPriceExtractor().extract_with_trace(frame)

    assert analysis.extraction.status is CurrentVisualPriceStatus.OK
    assert analysis.extraction.selected_y == float(y)
    assert analysis.extraction.price is not None
    assert analysis.extraction.price.roi_y == float(y)
    assert (analysis.trace.safe_top, analysis.trace.safe_bottom) == (12, 12)
    assert analysis.trace.decision_diagnostic == "candidate_available"


@pytest.mark.parametrize("y", [13, 774])
def test_clipped_but_sufficient_marker_is_available_near_real_roi_edges(
    y: int,
) -> None:
    frame = image(height=788, width=1174)
    marker(frame, y, effective_right=1062, right_gap=2)
    extractor = PocketOptionCurrentVisualPriceExtractor(
        effective_chart_right_x=1062,
    )

    analysis = extractor.extract_with_trace(frame)

    assert analysis.extraction.status is CurrentVisualPriceStatus.OK
    assert analysis.extraction.selected_y == float(y)
    assert (analysis.trace.safe_top, analysis.trace.safe_bottom) == (40, 40)
    assert y < analysis.trace.safe_top or y > 787 - analysis.trace.safe_bottom
    row = next(row for row in analysis.trace.row_evaluations if row.qualified)
    assert row.line_evidence is True
    assert row.label_support is True
    assert row.label_support_trace is not None
    assert row.label_support_trace.window_start_y == max(0, y - 20)
    assert row.label_support_trace.window_end_y == min(788, y + 21)


def test_partial_label_without_sufficient_line_near_bottom_is_unavailable() -> None:
    frame = image(height=788, width=1174)
    frame[786:788, 1010:1062] = CURRENT_PRICE_BLUE

    analysis = PocketOptionCurrentVisualPriceExtractor(
        effective_chart_right_x=1062,
    ).extract_with_trace(frame)

    assert analysis.extraction.status is (
        CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE
    )
    assert analysis.extraction.selected_y is None
    assert not any(row.line_evidence for row in analysis.trace.row_evaluations)
    assert analysis.trace.decision_diagnostic == "no_line_rows"


def test_vertical_wick_and_short_fragment_are_rejected() -> None:
    wick = image()
    cv2.line(wick, (99, 20), (99, 80), CURRENT_PRICE_BLUE, 1)
    fragment = image()
    cv2.line(fragment, (96, 50), (99, 50), CURRENT_PRICE_BLUE, 1)
    extractor = PocketOptionCurrentVisualPriceExtractor()
    assert (
        extractor.extract(wick).status
        is CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE
    )
    assert (
        extractor.extract(fragment).status
        is CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE
    )


def test_thick_line_uses_weighted_vertical_center() -> None:
    frame = image()
    for y in range(48, 53):
        marker(frame, y)
    result = PocketOptionCurrentVisualPriceExtractor().extract(frame)
    assert result.status is CurrentVisualPriceStatus.OK
    assert result.selected_y == 50.0


def test_equal_candidates_are_ambiguous() -> None:
    frame = image()
    marker(frame, 40)
    marker(frame, 60)
    result = PocketOptionCurrentVisualPriceExtractor().extract(frame)
    assert result.status is CurrentVisualPriceStatus.AMBIGUOUS_VISUAL_PRICE
    assert result.candidate_count == 2


def test_clearly_better_candidate_is_selected() -> None:
    frame = image()
    marker(frame, 40)
    line(frame, 60, start=80, end=94)
    frame[59, 99] = CURRENT_PRICE_BLUE
    frame[61, 99] = CURRENT_PRICE_BLUE
    result = PocketOptionCurrentVisualPriceExtractor().extract(frame)
    assert result.status is CurrentVisualPriceStatus.OK
    assert result.selected_y == 40.0


def test_valid_marker_can_be_low_confidence_with_strict_threshold() -> None:
    frame = image()
    line(frame, 50, start=80, end=94)
    frame[49, 99] = CURRENT_PRICE_BLUE
    frame[51, 99] = CURRENT_PRICE_BLUE

    result = PocketOptionCurrentVisualPriceExtractor(
        min_confidence=0.90,
    ).extract(frame)
    assert result.status is CurrentVisualPriceStatus.LOW_CONFIDENCE
    assert result.confidence is not None and result.confidence < 0.90


def test_diagnostics_coordinates_and_exact_normalization() -> None:
    frame = image(height=101, width=120)
    marker(frame, 25)
    result = PocketOptionCurrentVisualPriceExtractor().extract(frame)
    assert result.price is not None
    assert result.selected_x == 107.5
    assert result.price.roi_y == 25.0
    assert result.price.normalized_roi_y == 0.75
    assert result.price.roi_width == 120
    assert result.price.roi_height == 101
    assert result.price.source == "pocket_option_right_band_v1"
    assert result.diagnostic is not None
    for field in ("band_start=", "coverage=", "span=", "right_edge_gap=", "score="):
        assert field in result.diagnostic


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("right_band_ratio", -0.1),
        ("safe_top_ratio", float("nan")),
        ("min_line_run_ratio", 1.1),
        ("min_line_continuity_ratio", -0.1),
        ("max_line_start_offset_ratio", 1.1),
        ("max_line_gap_ratio", -0.1),
        ("label_zone_ratio", 1.1),
        ("label_vertical_radius_ratio", -0.1),
        ("min_label_support_row_ratio", 1.1),
        ("min_label_support_density_ratio", -0.1),
        ("min_confidence", 1.1),
        ("max_row_gap_px", -1),
        ("max_candidate_height_px", 1.5),
    ],
)
def test_invalid_parameters(name: str, value: object) -> None:
    with pytest.raises(ValueError):
        PocketOptionCurrentVisualPriceExtractor(**{name: value})  # type: ignore[arg-type]


def test_injected_mask_builder_receives_bgr_without_mutating_input() -> None:
    class RecordingMaskBuilder:
        received: np.ndarray | None = None

        def build(self, frame: np.ndarray) -> np.ndarray:
            self.received = frame
            mask = np.zeros(frame.shape[:2], dtype=np.uint8)
            mask[50, 80:95] = 255
            mask[47:54, 95:100] = 255
            return mask

    builder = RecordingMaskBuilder()
    frame = image(channels=4)
    original = frame.copy()
    result = PocketOptionCurrentVisualPriceExtractor(mask_builder=builder).extract(
        frame
    )
    assert result.status is CurrentVisualPriceStatus.OK
    assert builder.received is not None and builder.received.shape == (100, 100, 3)
    np.testing.assert_array_equal(frame, original)


def test_trace_preserves_ok_candidate_and_effective_configuration() -> None:
    frame = image(height=800, width=1161)
    marker(frame, 400, effective_right=1062)
    extractor = PocketOptionCurrentVisualPriceExtractor(effective_chart_right_x=1062)

    analysis = extractor.extract_with_trace(frame)

    assert analysis.extraction.status is CurrentVisualPriceStatus.OK
    assert analysis.trace.status is analysis.extraction.status
    assert analysis.trace.image_width == 1161
    assert analysis.trace.image_height == 800
    assert analysis.trace.effective_chart_right_x == 1062
    assert analysis.trace.effective_chart_right_source == "configured"
    assert (analysis.trace.band_start, analysis.trace.band_end) == (849, 1062)
    assert analysis.trace.band_width == 213
    assert (analysis.trace.safe_top, analysis.trace.safe_bottom) == (40, 40)
    assert analysis.trace.masked_pixel_count > 134
    assert len(analysis.trace.candidates) == 1
    candidate = analysis.trace.candidates[0]
    assert candidate.candidate_id == "price_candidate_000"
    assert candidate.selected is True
    assert candidate.x == analysis.extraction.selected_x == 955.0
    assert candidate.y == analysis.extraction.selected_y == 400.0
    assert candidate.row_start == candidate.row_end == 400
    assert candidate.coverage == 1.0
    assert candidate.span == 1.0
    assert candidate.right_edge_gap == 0
    assert candidate.score == analysis.extraction.confidence
    selected_row = next(row for row in analysis.trace.row_evaluations if row.qualified)
    assert selected_row.line_evidence is True
    assert selected_row.label_support is True
    assert selected_row.longest_run_ratio == 1.0
    assert selected_row.label_support_trace is not None


def test_trace_preserves_all_candidates_and_exact_selected_one() -> None:
    frame = image()
    marker(frame, 40)
    marker(frame, 60)

    analysis = PocketOptionCurrentVisualPriceExtractor().extract_with_trace(frame)

    assert analysis.extraction.status is (
        CurrentVisualPriceStatus.AMBIGUOUS_VISUAL_PRICE
    )
    assert len(analysis.trace.candidates) == 2
    assert [candidate.y for candidate in analysis.trace.candidates] == [40.0, 60.0]
    assert [candidate.selected for candidate in analysis.trace.candidates] == [
        True,
        False,
    ]


def test_no_qualifying_rows_trace_distinguishes_row_rejections() -> None:
    frame = image()
    cv2.line(frame, (99, 20), (99, 80), CURRENT_PRICE_BLUE, 1)

    analysis = PocketOptionCurrentVisualPriceExtractor().extract_with_trace(frame)

    assert analysis.extraction.status is (
        CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE
    )
    assert analysis.trace.candidates == ()
    counts = analysis.trace.rejection_counts
    assert counts.rows_with_mask_pixels == 61
    assert counts.rows_without_mask_pixels == 39
    assert counts.rejected_by_coverage == 61
    assert counts.rejected_by_span == 61
    assert counts.rejected_by_right_edge_gap == 0
    assert counts.qualifying_rows == 0
    assert counts.candidate_groups == 0


def test_no_candidate_trace_counts_right_edge_and_group_height_rejections() -> None:
    class RejectionMaskBuilder:
        def build(self, frame: np.ndarray) -> np.ndarray:
            mask = np.zeros(frame.shape[:2], dtype=np.uint8)
            mask[40:50, 80:95] = 255
            mask[20:31, 95:100] = 255
            mask[60:71, 95:100] = 255
            return mask

    analysis = PocketOptionCurrentVisualPriceExtractor(
        mask_builder=RejectionMaskBuilder(),
        label_vertical_radius_ratio=0.20,
    ).extract_with_trace(image())

    assert analysis.extraction.status is (
        CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE
    )
    counts = analysis.trace.rejection_counts
    assert counts.qualifying_rows == 10
    assert counts.candidate_groups == 1
    assert counts.rejected_by_group_height == 1
    assert analysis.trace.decision_diagnostic == "candidate_groups_rejected"


def test_invalid_image_trace_belongs_to_returned_extraction() -> None:
    analysis = PocketOptionCurrentVisualPriceExtractor().extract_with_trace(None)  # type: ignore[arg-type]

    assert analysis.extraction.status is CurrentVisualPriceStatus.INVALID_IMAGE
    assert analysis.trace.status is analysis.extraction.status
    assert analysis.trace.image_width is None
    assert analysis.trace.candidates == ()


def test_extract_with_trace_builds_mask_once() -> None:
    class CountingMaskBuilder:
        calls = 0

        def build(self, frame: np.ndarray) -> np.ndarray:
            self.calls += 1
            mask = np.zeros(frame.shape[:2], dtype=np.uint8)
            mask[50, 80:95] = 255
            mask[47:54, 95:100] = 255
            return mask

    builder = CountingMaskBuilder()
    extractor = PocketOptionCurrentVisualPriceExtractor(mask_builder=builder)

    analysis = extractor.extract_with_trace(image())

    assert analysis.extraction.status is CurrentVisualPriceStatus.OK
    assert builder.calls == 1
