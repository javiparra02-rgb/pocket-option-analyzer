from __future__ import annotations

from dataclasses import dataclass
from math import ceil, isfinite
from typing import Protocol

import cv2
import numpy as np

from pocket_option_analyzer.vision.models import (
    CurrentVisualPrice,
    CurrentVisualPriceExtraction,
    CurrentVisualPriceStatus,
)
from pocket_option_analyzer.vision.preprocessing import FrameValidator

from .pocket_option_current_price_mask_builder import (
    PocketOptionCurrentPriceMaskBuilder,
)


class _MaskBuilder(Protocol):
    def build(self, image: np.ndarray) -> np.ndarray: ...


@dataclass(frozen=True, slots=True)
class _Candidate:
    y: float
    x: float
    score: float
    row_start: int
    row_end: int
    coverage: float
    span: float
    right_edge_gap: int


class PocketOptionCurrentVisualPriceExtractor:
    """Localiza diagnósticamente una marca horizontal en el extremo derecho."""

    def __init__(
        self,
        *,
        right_band_ratio: float = 0.20,
        safe_top_ratio: float = 0.05,
        safe_bottom_ratio: float = 0.05,
        min_safe_top_px: int = 12,
        min_safe_bottom_px: int = 12,
        min_row_coverage_ratio: float = 0.20,
        min_horizontal_span_ratio: float = 0.50,
        max_right_edge_gap_px: int = 3,
        max_candidate_height_px: int = 7,
        max_row_gap_px: int = 1,
        min_confidence: float = 0.60,
        ambiguity_score_delta: float = 0.10,
        source: str = "pocket_option_right_band_v1",
        effective_chart_right_x: int | None = None,
        mask_builder: _MaskBuilder | None = None,
    ) -> None:
        ratios = {
            "right_band_ratio": right_band_ratio,
            "safe_top_ratio": safe_top_ratio,
            "safe_bottom_ratio": safe_bottom_ratio,
            "min_row_coverage_ratio": min_row_coverage_ratio,
            "min_horizontal_span_ratio": min_horizontal_span_ratio,
            "min_confidence": min_confidence,
            "ambiguity_score_delta": ambiguity_score_delta,
        }
        for name, value in ratios.items():
            if not isinstance(value, (int, float)) or not isfinite(value):
                raise ValueError(f"{name} debe ser un número finito.")
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} debe estar entre 0.0 y 1.0.")

        integers = {
            "min_safe_top_px": min_safe_top_px,
            "min_safe_bottom_px": min_safe_bottom_px,
            "max_right_edge_gap_px": max_right_edge_gap_px,
            "max_candidate_height_px": max_candidate_height_px,
            "max_row_gap_px": max_row_gap_px,
        }
        for name, value in integers.items():
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} debe ser un entero no negativo.")

        if not source:
            raise ValueError("source no puede estar vacío.")

        if effective_chart_right_x is not None and (
            not isinstance(effective_chart_right_x, int)
            or isinstance(effective_chart_right_x, bool)
            or effective_chart_right_x < 1
        ):
            raise ValueError("effective_chart_right_x debe ser un entero positivo.")

        self._right_band_ratio = float(right_band_ratio)
        self._safe_top_ratio = float(safe_top_ratio)
        self._safe_bottom_ratio = float(safe_bottom_ratio)
        self._min_safe_top_px = min_safe_top_px
        self._min_safe_bottom_px = min_safe_bottom_px
        self._min_row_coverage_ratio = float(min_row_coverage_ratio)
        self._min_horizontal_span_ratio = float(min_horizontal_span_ratio)
        self._max_right_edge_gap_px = max_right_edge_gap_px
        self._max_candidate_height_px = max_candidate_height_px
        self._max_row_gap_px = max_row_gap_px
        self._min_confidence = float(min_confidence)
        self._ambiguity_score_delta = float(ambiguity_score_delta)
        self._source = source
        self._effective_chart_right_x = effective_chart_right_x
        self._mask_builder = mask_builder or PocketOptionCurrentPriceMaskBuilder()

    def extract(self, image: np.ndarray) -> CurrentVisualPriceExtraction:
        if not FrameValidator.validate(image):
            return CurrentVisualPriceExtraction(
                price=None,
                status=CurrentVisualPriceStatus.INVALID_IMAGE,
                diagnostic="invalid_image: expected non-empty uint8 BGR/BGRA matrix",
            )

        bgr = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR) if image.shape[2] == 4 else image
        height, width = bgr.shape[:2]
        if self._effective_chart_right_x is None:
            effective_chart_right_x = width
            effective_chart_right_source = "image_width_fallback"
        else:
            effective_chart_right_x = self._effective_chart_right_x
            effective_chart_right_source = "configured"
            if effective_chart_right_x > width:
                raise ValueError(
                    "effective_chart_right_x debe ser menor o igual que image_width."
                )
        band_end = effective_chart_right_x
        band_width = max(1, ceil(effective_chart_right_x * self._right_band_ratio))
        band_start = max(0, band_end - band_width)
        mask = self._mask_builder.build(bgr)
        if mask.shape != (height, width):
            raise ValueError(
                "mask_builder debe devolver una máscara 2D del tamaño del ROI."
            )

        masked_pixel_count = int(np.count_nonzero(mask))
        candidates = self._find_candidates(mask, band_start, band_end, band_width)
        if not candidates:
            return CurrentVisualPriceExtraction(
                price=None,
                status=CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE,
                diagnostic=self._diagnostic(
                    band_start=band_start,
                    band_end=band_end,
                    band_width=band_width,
                    image_width=width,
                    effective_chart_right_x=effective_chart_right_x,
                    effective_chart_right_source=effective_chart_right_source,
                    masked_pixel_count=masked_pixel_count,
                    safe_top=max(
                        ceil(height * self._safe_top_ratio), self._min_safe_top_px
                    ),
                    safe_bottom=max(
                        ceil(height * self._safe_bottom_ratio),
                        self._min_safe_bottom_px,
                    ),
                    selected=None,
                    reason="no_qualifying_rows",
                ),
            )

        candidates.sort(key=lambda candidate: (-candidate.score, candidate.y))
        selected = candidates[0]
        safe_top = max(ceil(height * self._safe_top_ratio), self._min_safe_top_px)
        safe_bottom = max(
            ceil(height * self._safe_bottom_ratio), self._min_safe_bottom_px
        )
        diagnostic = self._diagnostic(
            band_start=band_start,
            band_end=band_end,
            band_width=band_width,
            image_width=width,
            effective_chart_right_x=effective_chart_right_x,
            effective_chart_right_source=effective_chart_right_source,
            masked_pixel_count=masked_pixel_count,
            safe_top=safe_top,
            safe_bottom=safe_bottom,
            selected=selected,
            reason=None,
        )
        common = {
            "price": None,
            "candidate_count": len(candidates),
            "selected_x": selected.x,
            "selected_y": selected.y,
            "confidence": selected.score,
            "diagnostic": diagnostic,
        }

        if len(candidates) > 1 and (
            selected.score - candidates[1].score <= self._ambiguity_score_delta
        ):
            return CurrentVisualPriceExtraction(
                status=CurrentVisualPriceStatus.AMBIGUOUS_VISUAL_PRICE,
                **common,
            )
        if selected.y < safe_top or selected.y > height - 1 - safe_bottom:
            return CurrentVisualPriceExtraction(
                status=CurrentVisualPriceStatus.CANDIDATE_OUTSIDE_SAFE_REGION,
                **common,
            )
        if selected.score < self._min_confidence:
            return CurrentVisualPriceExtraction(
                status=CurrentVisualPriceStatus.LOW_CONFIDENCE,
                **common,
            )

        price = CurrentVisualPrice(
            roi_y=selected.y,
            normalized_roi_y=1.0 - selected.y / (height - 1),
            roi_width=width,
            roi_height=height,
            source=self._source,
            confidence=selected.score,
        )
        return CurrentVisualPriceExtraction(
            price=price,
            status=CurrentVisualPriceStatus.OK,
            candidate_count=len(candidates),
            selected_x=selected.x,
            selected_y=selected.y,
            confidence=selected.score,
            diagnostic=diagnostic,
        )

    def _find_candidates(
        self,
        mask: np.ndarray,
        band_start: int,
        band_end: int,
        band_width: int,
    ) -> list[_Candidate]:
        band = mask[:, band_start:band_end] != 0
        qualifying: list[tuple[int, np.ndarray, float, float, int]] = []
        for y, row in enumerate(band):
            xs = np.flatnonzero(row)
            if xs.size == 0:
                continue
            coverage = float(xs.size / band_width)
            span = float((xs[-1] - xs[0] + 1) / band_width)
            candidate_last_x = band_start + int(xs[-1])
            right_edge_gap = int(band_end - 1 - candidate_last_x)
            if (
                coverage >= self._min_row_coverage_ratio
                and span >= self._min_horizontal_span_ratio
                and right_edge_gap <= self._max_right_edge_gap_px
            ):
                qualifying.append((y, xs, coverage, span, right_edge_gap))

        groups: list[list[tuple[int, np.ndarray, float, float, int]]] = []
        for row in qualifying:
            if groups and row[0] - groups[-1][-1][0] <= self._max_row_gap_px + 1:
                groups[-1].append(row)
            else:
                groups.append([row])

        candidates: list[_Candidate] = []
        for group in groups:
            row_start = group[0][0]
            row_end = group[-1][0]
            if row_end - row_start + 1 > self._max_candidate_height_px:
                continue
            weights = np.array([row[1].size for row in group], dtype=np.float64)
            ys = np.array([row[0] for row in group], dtype=np.float64)
            x_centers = np.array(
                [(row[1][0] + row[1][-1]) / 2 + band_start for row in group],
                dtype=np.float64,
            )
            coverage = float(np.average([row[2] for row in group], weights=weights))
            span = float(np.average([row[3] for row in group], weights=weights))
            right_edge_gap = min(row[4] for row in group)
            right_support = 1.0 - right_edge_gap / max(
                1, self._max_right_edge_gap_px + 1
            )
            score = min(1.0, 0.55 * coverage + 0.35 * span + 0.10 * right_support)
            candidates.append(
                _Candidate(
                    y=float(np.average(ys, weights=weights)),
                    x=float(np.average(x_centers, weights=weights)),
                    score=score,
                    row_start=row_start,
                    row_end=row_end,
                    coverage=coverage,
                    span=span,
                    right_edge_gap=right_edge_gap,
                )
            )
        return candidates

    @staticmethod
    def _diagnostic(
        *,
        image_width: int,
        effective_chart_right_x: int,
        effective_chart_right_source: str,
        band_start: int,
        band_end: int,
        band_width: int,
        masked_pixel_count: int,
        safe_top: int,
        safe_bottom: int,
        selected: _Candidate | None,
        reason: str | None,
    ) -> str:
        base = (
            f"image_width={image_width}; "
            f"effective_chart_right_x={effective_chart_right_x}; "
            f"effective_chart_right_source={effective_chart_right_source}; "
            f"band_start={band_start}; band_end={band_end}; "
            f"band_width={band_width}; masked_pixel_count={masked_pixel_count}; "
            f"safe_top={safe_top}; safe_bottom={safe_bottom}"
        )
        if selected is None:
            return f"{base}; selected=none; reason={reason}"
        return (
            f"{base}; rows={selected.row_start}-{selected.row_end}; "
            f"coverage={selected.coverage:.4f}; span={selected.span:.4f}; "
            f"right_edge_gap={selected.right_edge_gap}; score={selected.score:.4f}"
        )
