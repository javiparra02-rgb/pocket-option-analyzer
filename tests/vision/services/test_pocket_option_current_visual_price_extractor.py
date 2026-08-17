from __future__ import annotations

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
    line(frame, 50, color=color)
    assert (
        PocketOptionCurrentVisualPriceExtractor().extract(frame).status
        is CurrentVisualPriceStatus.OK
    )


def test_dark_roi_has_no_candidate() -> None:
    result = PocketOptionCurrentVisualPriceExtractor().extract(image())
    assert result.status is CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE


def test_effective_chart_right_detects_blue_line_before_side_panel() -> None:
    frame = image(height=800, width=1161)
    line(frame, 400, start=928, end=1061)

    result = PocketOptionCurrentVisualPriceExtractor(
        effective_chart_right_x=1062
    ).extract(frame)

    assert result.status is CurrentVisualPriceStatus.OK
    assert result.price is not None
    assert result.selected_x == 994.5


def test_image_width_fallback_does_not_treat_side_panel_as_chart() -> None:
    frame = image(height=800, width=1161)
    line(frame, 400, start=928, end=1061)

    result = PocketOptionCurrentVisualPriceExtractor().extract(frame)

    assert result.status is CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE
    assert result.diagnostic is not None
    assert "effective_chart_right_source=image_width_fallback" in result.diagnostic


def test_effective_chart_band_geometry_is_exact() -> None:
    frame = image(height=800, width=1161)
    line(frame, 400, start=928, end=1061)

    result = PocketOptionCurrentVisualPriceExtractor(
        effective_chart_right_x=1062
    ).extract(frame)

    assert result.diagnostic is not None
    assert "band_start=849; band_end=1062; band_width=213" in result.diagnostic


def test_right_edge_gap_uses_effective_chart_edge() -> None:
    frame = image(height=800, width=1161)
    line(frame, 400, start=928, end=1059)

    result = PocketOptionCurrentVisualPriceExtractor(
        effective_chart_right_x=1062
    ).extract(frame)

    assert result.status is CurrentVisualPriceStatus.OK
    assert result.diagnostic is not None
    assert "right_edge_gap=2" in result.diagnostic


def test_diagnostic_contains_effective_edge_and_mask_fields() -> None:
    frame = image(height=800, width=1161)
    line(frame, 400, start=928, end=1061)

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
        "masked_pixel_count=134",
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


def test_y_11_is_outside_safe_region_and_y_12_is_accepted() -> None:
    outside = image()
    line(outside, 11)
    inside = image()
    line(inside, 12)
    extractor = PocketOptionCurrentVisualPriceExtractor()
    rejected = extractor.extract(outside)
    assert rejected.status is CurrentVisualPriceStatus.CANDIDATE_OUTSIDE_SAFE_REGION
    assert rejected.selected_y == 11.0
    assert extractor.extract(inside).status is CurrentVisualPriceStatus.OK


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
    cv2.rectangle(frame, (80, 48), (99, 52), CURRENT_PRICE_BLUE, -1)
    result = PocketOptionCurrentVisualPriceExtractor().extract(frame)
    assert result.status is CurrentVisualPriceStatus.OK
    assert result.selected_y == 50.0


def test_equal_candidates_are_ambiguous() -> None:
    frame = image()
    line(frame, 40)
    line(frame, 60)
    result = PocketOptionCurrentVisualPriceExtractor().extract(frame)
    assert result.status is CurrentVisualPriceStatus.AMBIGUOUS_VISUAL_PRICE
    assert result.candidate_count == 2


def test_clearly_better_candidate_is_selected() -> None:
    frame = image()
    line(frame, 40)
    cv2.line(frame, (90, 60), (99, 60), CURRENT_PRICE_BLUE, 1)
    result = PocketOptionCurrentVisualPriceExtractor().extract(frame)
    assert result.status is CurrentVisualPriceStatus.OK
    assert result.selected_y == 40.0


def test_qualifying_sparse_row_can_be_low_confidence() -> None:
    class SparseMaskBuilder:
        def build(self, frame: np.ndarray) -> np.ndarray:
            mask = np.zeros(frame.shape[:2], dtype=np.uint8)
            mask[50, [80, 81, 88, 99]] = 255
            return mask

    result = PocketOptionCurrentVisualPriceExtractor(
        mask_builder=SparseMaskBuilder()
    ).extract(image())
    assert result.status is CurrentVisualPriceStatus.LOW_CONFIDENCE
    assert result.confidence is not None and result.confidence < 0.60


def test_diagnostics_coordinates_and_exact_normalization() -> None:
    frame = image(height=101, width=120)
    line(frame, 25, start=96)
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
            mask[50, 80:100] = 255
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
    line(frame, 400, start=928, end=1061)
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
    assert analysis.trace.masked_pixel_count == 134
    assert len(analysis.trace.candidates) == 1
    candidate = analysis.trace.candidates[0]
    assert candidate.candidate_id == "price_candidate_000"
    assert candidate.selected is True
    assert candidate.x == analysis.extraction.selected_x == 994.5
    assert candidate.y == analysis.extraction.selected_y == 400.0
    assert candidate.row_start == candidate.row_end == 400
    assert candidate.coverage == 134 / 213
    assert candidate.span == 134 / 213
    assert candidate.right_edge_gap == 0
    assert candidate.score == analysis.extraction.confidence


def test_trace_preserves_all_candidates_and_exact_selected_one() -> None:
    frame = image()
    line(frame, 40)
    line(frame, 60)

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
            mask[20, 80:96] = 255
            mask[40:50, 80:100] = 255
            return mask

    analysis = PocketOptionCurrentVisualPriceExtractor(
        mask_builder=RejectionMaskBuilder()
    ).extract_with_trace(image())

    assert analysis.extraction.status is (
        CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE
    )
    counts = analysis.trace.rejection_counts
    assert counts.rejected_by_right_edge_gap == 1
    assert counts.qualifying_rows == 10
    assert counts.candidate_groups == 1
    assert counts.rejected_by_group_height == 1


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
            mask[50, 80:100] = 255
            return mask

    builder = CountingMaskBuilder()
    extractor = PocketOptionCurrentVisualPriceExtractor(mask_builder=builder)

    analysis = extractor.extract_with_trace(image())

    assert analysis.extraction.status is CurrentVisualPriceStatus.OK
    assert builder.calls == 1
