from __future__ import annotations

from dataclasses import dataclass
from math import ceil, isfinite
from typing import Protocol

import cv2
import numpy as np

from pocket_option_analyzer.vision.models import (
    CurrentVisualPrice,
    CurrentVisualPriceAnalysis,
    CurrentVisualPriceCandidateTrace,
    CurrentVisualPriceDetectionTrace,
    CurrentVisualPriceExtraction,
    CurrentVisualPriceLabelSupportTrace,
    CurrentVisualPriceRejectionCounts,
    CurrentVisualPriceRowEvaluationTrace,
    CurrentVisualPriceRowRejectionReason,
    CurrentVisualPriceSearchConstraints,
    CurrentVisualPriceSearchPlan,
    CurrentVisualPriceSearchPlanReason,
    CurrentVisualPriceSearchPlanStatus,
    CurrentVisualPriceSearchWindow,
    CurrentVisualPriceSearchWindowEvaluationTrace,
    CurrentVisualPriceSearchWindowOrigin,
    CurrentVisualPriceSemanticCandidateGroupTrace,
    CurrentVisualPriceSemanticResolutionReason,
    CurrentVisualPriceSemanticResolutionStatus,
    CurrentVisualPriceSemanticSearchMode,
    CurrentVisualPriceSemanticSearchTrace,
    CurrentVisualPriceStatus,
)
from pocket_option_analyzer.vision.preprocessing import FrameValidator

from .current_visual_price_search_window_resolver import (
    CurrentVisualPriceSearchWindowResolver,
)
from .pocket_option_current_price_mask_builder import (
    PocketOptionCurrentPriceMaskBuilder,
)
from .pocket_option_current_visual_price_search_window_resolver import (
    PocketOptionCurrentVisualPriceSearchWindowResolver,
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


@dataclass(frozen=True, slots=True)
class _SupportedRun:
    start: int
    end: int
    masked_pixels: int

    @property
    def span_pixels(self) -> int:
        return self.end - self.start + 1

    @property
    def continuity(self) -> float:
        return self.masked_pixels / self.span_pixels


@dataclass(frozen=True, slots=True)
class _RowMetrics:
    y: int
    xs: np.ndarray
    coverage: float
    span: float
    right_edge_gap: int
    longest_run: np.ndarray
    component_count: int
    line_run: _SupportedRun
    line_run_span_ratio: float
    line_evidence: bool
    line_rejection_reasons: tuple[CurrentVisualPriceRowRejectionReason, ...]


@dataclass(frozen=True, slots=True)
class _CandidateSearch:
    candidates: tuple[_Candidate, ...]
    rejection_counts: CurrentVisualPriceRejectionCounts
    row_evaluations: tuple[CurrentVisualPriceRowEvaluationTrace, ...]
    decision_diagnostic: str


@dataclass(frozen=True, slots=True)
class _QualifiedSemanticCandidate:
    semantic_candidate_id: str
    candidate: _Candidate
    window: CurrentVisualPriceSearchWindow
    line_hypothesis_ids: tuple[str, ...]
    qualified_row_ids: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class _SemanticCandidateGroup:
    group_id: str
    members: tuple[_QualifiedSemanticCandidate, ...]
    line_hypothesis_ids: tuple[str, ...]
    representative: _QualifiedSemanticCandidate


class _DisjointSet:
    def __init__(self, size: int) -> None:
        self._parents = list(range(size))

    def find(self, item: int) -> int:
        parent = self._parents[item]
        if parent != item:
            self._parents[item] = self.find(parent)
        return self._parents[item]

    def union(self, left: int, right: int) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        if left_root < right_root:
            self._parents[right_root] = left_root
        else:
            self._parents[left_root] = right_root


# El score refleja las dos señales del detector: geometría/continuidad de línea
# y soporte de etiqueta cercano. Los pesos suman uno para conservar [0, 1].
_LINE_SPAN_SCORE_WEIGHT = 0.45
_LINE_CONTINUITY_SCORE_WEIGHT = 0.30
_LABEL_SUPPORT_SCORE_WEIGHT = 0.25


class PocketOptionCurrentVisualPriceExtractor:
    """Localiza una línea de precio con soporte geométrico de etiqueta.

    Coverage, span y right-edge gap se conservan como métricas diagnósticas
    compatibles. La calificación productiva usa continuidad horizontal y
    soporte de etiqueta cercano, sin depender de un glifo terminal.
    """

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
        min_line_run_ratio: float = 0.70,
        min_line_continuity_ratio: float = 0.90,
        max_line_start_offset_ratio: float = 0.05,
        max_line_gap_ratio: float = 0.01,
        label_zone_ratio: float = 0.25,
        label_vertical_radius_ratio: float = 0.025,
        min_label_support_row_ratio: float = 0.20,
        min_label_support_density_ratio: float = 0.05,
        max_candidate_height_px: int = 7,
        max_row_gap_px: int = 1,
        min_confidence: float = 0.60,
        ambiguity_score_delta: float = 0.10,
        source: str = "pocket_option_right_band_v1",
        effective_chart_right_x: int | None = None,
        mask_builder: _MaskBuilder | None = None,
        search_window_resolver: CurrentVisualPriceSearchWindowResolver | None = None,
    ) -> None:
        ratios = {
            "right_band_ratio": right_band_ratio,
            "safe_top_ratio": safe_top_ratio,
            "safe_bottom_ratio": safe_bottom_ratio,
            "min_row_coverage_ratio": min_row_coverage_ratio,
            "min_horizontal_span_ratio": min_horizontal_span_ratio,
            "min_line_run_ratio": min_line_run_ratio,
            "min_line_continuity_ratio": min_line_continuity_ratio,
            "max_line_start_offset_ratio": max_line_start_offset_ratio,
            "max_line_gap_ratio": max_line_gap_ratio,
            "label_zone_ratio": label_zone_ratio,
            "label_vertical_radius_ratio": label_vertical_radius_ratio,
            "min_label_support_row_ratio": min_label_support_row_ratio,
            "min_label_support_density_ratio": min_label_support_density_ratio,
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
        self._min_line_run_ratio = float(min_line_run_ratio)
        self._min_line_continuity_ratio = float(min_line_continuity_ratio)
        self._max_line_start_offset_ratio = float(max_line_start_offset_ratio)
        self._max_line_gap_ratio = float(max_line_gap_ratio)
        self._label_zone_ratio = float(label_zone_ratio)
        self._label_vertical_radius_ratio = float(label_vertical_radius_ratio)
        self._min_label_support_row_ratio = float(min_label_support_row_ratio)
        self._min_label_support_density_ratio = float(min_label_support_density_ratio)
        self._max_candidate_height_px = max_candidate_height_px
        self._max_row_gap_px = max_row_gap_px
        self._min_confidence = float(min_confidence)
        self._ambiguity_score_delta = float(ambiguity_score_delta)
        self._source = source
        self._effective_chart_right_x = effective_chart_right_x
        self._mask_builder = mask_builder or PocketOptionCurrentPriceMaskBuilder()
        self._search_window_resolver = (
            search_window_resolver
            or PocketOptionCurrentVisualPriceSearchWindowResolver()
        )

    def extract(self, image: np.ndarray) -> CurrentVisualPriceExtraction:
        return self.extract_with_trace(image).extraction

    def extract_with_trace(self, image: np.ndarray) -> CurrentVisualPriceAnalysis:
        """Extrae el precio y registra la evidencia durante la misma pasada."""

        if not FrameValidator.validate(image):
            extraction = CurrentVisualPriceExtraction(
                price=None,
                status=CurrentVisualPriceStatus.INVALID_IMAGE,
                diagnostic="invalid_image: expected non-empty uint8 BGR/BGRA matrix",
            )
            return CurrentVisualPriceAnalysis(
                extraction=extraction,
                trace=CurrentVisualPriceDetectionTrace(
                    status=extraction.status,
                    image_width=None,
                    image_height=None,
                    effective_chart_right_x=None,
                    effective_chart_right_source=None,
                    band_start=None,
                    band_end=None,
                    band_width=None,
                    safe_top=None,
                    safe_bottom=None,
                    masked_pixel_count=0,
                    candidates=(),
                    rejection_counts=CurrentVisualPriceRejectionCounts(),
                    decision_diagnostic="invalid_image",
                ),
            )

        bgr = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR) if image.shape[2] == 4 else image
        height, width = bgr.shape[:2]
        mask = self._mask_builder.build(bgr)
        if mask.dtype != np.uint8 or mask.shape != (height, width):
            raise ValueError(
                "mask_builder debe devolver una máscara uint8 2D del tamaño del ROI."
            )
        masked_pixel_count = int(np.count_nonzero(mask))
        safe_top = max(ceil(height * self._safe_top_ratio), self._min_safe_top_px)
        safe_bottom = max(
            ceil(height * self._safe_bottom_ratio), self._min_safe_bottom_px
        )
        if self._effective_chart_right_x is not None:
            return self._extract_fixed_override(
                mask=mask,
                image_width=width,
                image_height=height,
                masked_pixel_count=masked_pixel_count,
                safe_top=safe_top,
                safe_bottom=safe_bottom,
            )
        constraints = CurrentVisualPriceSearchConstraints(
            image_width=width,
            image_height=height,
            right_band_ratio=self._right_band_ratio,
            max_line_gap_ratio=self._max_line_gap_ratio,
            max_line_start_offset_ratio=self._max_line_start_offset_ratio,
            min_line_run_ratio=self._min_line_run_ratio,
            label_zone_ratio=self._label_zone_ratio,
            label_vertical_radius_ratio=self._label_vertical_radius_ratio,
            max_row_gap_px=self._max_row_gap_px,
            max_candidate_height_px=self._max_candidate_height_px,
        )
        plan = self._search_window_resolver.resolve(
            mask=mask,
            constraints=constraints,
        )
        return self._extract_dynamic(
            mask=mask,
            plan=plan,
            image_width=width,
            image_height=height,
            masked_pixel_count=masked_pixel_count,
            safe_top=safe_top,
            safe_bottom=safe_bottom,
        )

    def _extract_fixed_override(
        self,
        *,
        mask: np.ndarray,
        image_width: int,
        image_height: int,
        masked_pixel_count: int,
        safe_top: int,
        safe_bottom: int,
    ) -> CurrentVisualPriceAnalysis:
        effective_chart_right_x = self._effective_chart_right_x
        assert effective_chart_right_x is not None
        if effective_chart_right_x > image_width:
            raise ValueError(
                "effective_chart_right_x debe ser menor o igual que image_width."
            )
        band_end = effective_chart_right_x
        band_width = max(1, ceil(effective_chart_right_x * self._right_band_ratio))
        band_start = max(0, band_end - band_width)
        window = CurrentVisualPriceSearchWindow(
            window_id="fixed_override_window_000",
            start_x=band_start,
            end_x=band_end,
            origin=CurrentVisualPriceSearchWindowOrigin.FIXED_OVERRIDE,
        )
        search = self._search_candidates(mask, band_start, band_end, band_width)
        semantic_trace = CurrentVisualPriceSemanticSearchTrace(
            mode=CurrentVisualPriceSemanticSearchMode.FIXED_OVERRIDE,
            plan_status=CurrentVisualPriceSearchPlanStatus.AVAILABLE,
            plan_reason=CurrentVisualPriceSearchPlanReason.FIXED_OVERRIDE,
            total_proposed_window_count=1,
            evaluated_window_count=1,
            windows=(window,),
            window_evaluations=(
                CurrentVisualPriceSearchWindowEvaluationTrace(
                    window_id=window.window_id,
                    decision_diagnostic=search.decision_diagnostic,
                    candidate_count=len(search.candidates),
                    semantic_candidate_ids=tuple(
                        f"fixed_candidate_{index:03d}"
                        for index in range(len(search.candidates))
                    ),
                ),
            ),
            semantic_groups=(),
            resolution_status=CurrentVisualPriceSemanticResolutionStatus.BYPASSED,
            resolution_reason=CurrentVisualPriceSemanticResolutionReason.FIXED_OVERRIDE,
        )
        return self._resolve_candidates(
            candidates=tuple(
                sorted(
                    search.candidates,
                    key=lambda candidate: (-candidate.score, candidate.y),
                )
            ),
            search=search,
            image_width=image_width,
            image_height=image_height,
            effective_chart_right_x=effective_chart_right_x,
            effective_chart_right_source="configured",
            band_start=band_start,
            band_end=band_end,
            band_width=band_width,
            safe_top=safe_top,
            safe_bottom=safe_bottom,
            masked_pixel_count=masked_pixel_count,
            semantic_search=semantic_trace,
            semantic_ambiguity=False,
        )

    def _extract_dynamic(
        self,
        *,
        mask: np.ndarray,
        plan: CurrentVisualPriceSearchPlan,
        image_width: int,
        image_height: int,
        masked_pixel_count: int,
        safe_top: int,
        safe_bottom: int,
    ) -> CurrentVisualPriceAnalysis:
        if plan.status is CurrentVisualPriceSearchPlanStatus.UNAVAILABLE:
            semantic_trace = CurrentVisualPriceSemanticSearchTrace(
                mode=CurrentVisualPriceSemanticSearchMode.DYNAMIC,
                plan_status=plan.status,
                plan_reason=plan.reason,
                total_proposed_window_count=plan.total_proposed_window_count,
                evaluated_window_count=0,
                windows=plan.windows,
                window_evaluations=(),
                semantic_groups=(),
                resolution_status=(
                    CurrentVisualPriceSemanticResolutionStatus.UNAVAILABLE
                ),
                resolution_reason=(
                    CurrentVisualPriceSemanticResolutionReason.SEARCH_PLAN_UNAVAILABLE
                ),
                full_window_set_sha256=plan.full_window_set_sha256,
            )
            extraction = CurrentVisualPriceExtraction(
                price=None,
                status=CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE,
                diagnostic=(
                    "semantic_search_unavailable; "
                    f"plan_reason={plan.reason.value}; "
                    f"masked_pixel_count={masked_pixel_count}"
                ),
            )
            return self._analysis(
                extraction=extraction,
                image_width=image_width,
                image_height=image_height,
                effective_chart_right_x=None,
                effective_chart_right_source="semantic_resolver",
                band_start=None,
                band_end=None,
                band_width=None,
                safe_top=safe_top,
                safe_bottom=safe_bottom,
                masked_pixel_count=masked_pixel_count,
                candidates=(),
                selected=None,
                rejection_counts=self._whole_image_rejection_counts(mask),
                row_evaluations=(),
                decision_diagnostic=plan.reason.value,
                semantic_search=semantic_trace,
            )

        searches: dict[str, _CandidateSearch] = {}
        qualified: list[_QualifiedSemanticCandidate] = []
        evaluations: list[CurrentVisualPriceSearchWindowEvaluationTrace] = []
        for window in plan.windows:
            search = self._search_candidates(
                mask,
                window.start_x,
                window.end_x,
                window.width,
            )
            searches[window.window_id] = search
            ids: list[str] = []
            for index, candidate in enumerate(search.candidates):
                qualified_row_ids = self._candidate_qualified_row_ids(
                    candidate=candidate,
                    search=search,
                )
                line_ids = self._candidate_line_hypothesis_ids(
                    candidate=candidate,
                    search=search,
                    plan=plan,
                )
                if not line_ids:
                    continue
                candidate_id = f"{window.window_id}:candidate_{index:03d}"
                ids.append(candidate_id)
                qualified.append(
                    _QualifiedSemanticCandidate(
                        semantic_candidate_id=candidate_id,
                        candidate=candidate,
                        window=window,
                        line_hypothesis_ids=line_ids,
                        qualified_row_ids=qualified_row_ids,
                    )
                )
            evaluations.append(
                CurrentVisualPriceSearchWindowEvaluationTrace(
                    window_id=window.window_id,
                    decision_diagnostic=search.decision_diagnostic,
                    candidate_count=len(ids),
                    semantic_candidate_ids=tuple(ids),
                )
            )

        groups = self._semantic_candidate_groups(tuple(qualified))
        group_traces = tuple(self._semantic_group_trace(group) for group in groups)
        if not groups:
            representative_window = max(
                plan.windows,
                key=lambda window: (window.end_x, window.start_x, window.window_id),
            )
            representative_search = searches[representative_window.window_id]
            semantic_trace = CurrentVisualPriceSemanticSearchTrace(
                mode=CurrentVisualPriceSemanticSearchMode.DYNAMIC,
                plan_status=plan.status,
                plan_reason=plan.reason,
                total_proposed_window_count=plan.total_proposed_window_count,
                evaluated_window_count=len(evaluations),
                windows=plan.windows,
                window_evaluations=tuple(evaluations),
                semantic_groups=(),
                resolution_status=(
                    CurrentVisualPriceSemanticResolutionStatus.UNAVAILABLE
                ),
                resolution_reason=(
                    CurrentVisualPriceSemanticResolutionReason.NO_QUALIFYING_CANDIDATES
                ),
            )
            extraction = CurrentVisualPriceExtraction(
                price=None,
                status=CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE,
                diagnostic=(
                    "semantic_windows_without_qualifying_candidate; "
                    f"windows={len(plan.windows)}"
                ),
            )
            counts = representative_search.rejection_counts
            semantic_counts = CurrentVisualPriceRejectionCounts(
                rows_without_mask_pixels=counts.rows_without_mask_pixels,
                rows_with_mask_pixels=counts.rows_with_mask_pixels,
                rejected_by_coverage=counts.rejected_by_coverage,
                rejected_by_span=counts.rejected_by_span,
                rejected_by_right_edge_gap=counts.rejected_by_right_edge_gap,
                qualifying_rows=counts.qualifying_rows,
                candidate_groups=0,
                rejected_by_group_height=0,
                line_evidence_rows=counts.line_evidence_rows,
                rejected_by_label_support=counts.rejected_by_label_support,
            )
            return self._analysis(
                extraction=extraction,
                image_width=image_width,
                image_height=image_height,
                effective_chart_right_x=representative_window.end_x,
                effective_chart_right_source="semantic_resolver",
                band_start=representative_window.start_x,
                band_end=representative_window.end_x,
                band_width=representative_window.width,
                safe_top=safe_top,
                safe_bottom=safe_bottom,
                masked_pixel_count=masked_pixel_count,
                candidates=(),
                selected=None,
                rejection_counts=semantic_counts,
                row_evaluations=representative_search.row_evaluations,
                decision_diagnostic="semantic_windows_without_qualifying_candidate",
                semantic_search=semantic_trace,
            )

        representatives = tuple(group.representative.candidate for group in groups)
        representative_group = groups[0]
        representative_window = representative_group.representative.window
        representative_search = searches[representative_window.window_id]
        if len(groups) > 1:
            semantic_trace = CurrentVisualPriceSemanticSearchTrace(
                mode=CurrentVisualPriceSemanticSearchMode.DYNAMIC,
                plan_status=plan.status,
                plan_reason=plan.reason,
                total_proposed_window_count=plan.total_proposed_window_count,
                evaluated_window_count=len(evaluations),
                windows=plan.windows,
                window_evaluations=tuple(evaluations),
                semantic_groups=group_traces,
                resolution_status=(
                    CurrentVisualPriceSemanticResolutionStatus.AMBIGUOUS
                ),
                resolution_reason=(
                    CurrentVisualPriceSemanticResolutionReason.MULTIPLE_SEMANTIC_PRICES
                ),
            )
            return self._resolve_candidates(
                candidates=representatives,
                search=representative_search,
                image_width=image_width,
                image_height=image_height,
                effective_chart_right_x=representative_window.end_x,
                effective_chart_right_source="semantic_resolver",
                band_start=representative_window.start_x,
                band_end=representative_window.end_x,
                band_width=representative_window.width,
                safe_top=safe_top,
                safe_bottom=safe_bottom,
                masked_pixel_count=masked_pixel_count,
                semantic_search=semantic_trace,
                semantic_ambiguity=True,
            )

        semantic_trace = CurrentVisualPriceSemanticSearchTrace(
            mode=CurrentVisualPriceSemanticSearchMode.DYNAMIC,
            plan_status=plan.status,
            plan_reason=plan.reason,
            total_proposed_window_count=plan.total_proposed_window_count,
            evaluated_window_count=len(evaluations),
            windows=plan.windows,
            window_evaluations=tuple(evaluations),
            semantic_groups=group_traces,
            resolution_status=CurrentVisualPriceSemanticResolutionStatus.AVAILABLE,
            resolution_reason=(
                CurrentVisualPriceSemanticResolutionReason.UNIQUE_SEMANTIC_PRICE
            ),
            selected_group_id=representative_group.group_id,
        )
        return self._resolve_candidates(
            candidates=representatives,
            search=representative_search,
            image_width=image_width,
            image_height=image_height,
            effective_chart_right_x=representative_window.end_x,
            effective_chart_right_source="semantic_resolver",
            band_start=representative_window.start_x,
            band_end=representative_window.end_x,
            band_width=representative_window.width,
            safe_top=safe_top,
            safe_bottom=safe_bottom,
            masked_pixel_count=masked_pixel_count,
            semantic_search=semantic_trace,
            semantic_ambiguity=False,
        )

    def _resolve_candidates(
        self,
        *,
        candidates: tuple[_Candidate, ...],
        search: _CandidateSearch,
        image_width: int,
        image_height: int,
        effective_chart_right_x: int,
        effective_chart_right_source: str,
        band_start: int,
        band_end: int,
        band_width: int,
        safe_top: int,
        safe_bottom: int,
        masked_pixel_count: int,
        semantic_search: CurrentVisualPriceSemanticSearchTrace,
        semantic_ambiguity: bool,
    ) -> CurrentVisualPriceAnalysis:
        if not candidates:
            extraction = CurrentVisualPriceExtraction(
                price=None,
                status=CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE,
                diagnostic=self._diagnostic(
                    band_start=band_start,
                    band_end=band_end,
                    band_width=band_width,
                    image_width=image_width,
                    effective_chart_right_x=effective_chart_right_x,
                    effective_chart_right_source=effective_chart_right_source,
                    masked_pixel_count=masked_pixel_count,
                    safe_top=safe_top,
                    safe_bottom=safe_bottom,
                    selected=None,
                    reason=search.decision_diagnostic,
                ),
            )
            return self._analysis(
                extraction=extraction,
                image_width=image_width,
                image_height=image_height,
                effective_chart_right_x=effective_chart_right_x,
                effective_chart_right_source=effective_chart_right_source,
                band_start=band_start,
                band_end=band_end,
                band_width=band_width,
                safe_top=safe_top,
                safe_bottom=safe_bottom,
                masked_pixel_count=masked_pixel_count,
                candidates=(),
                selected=None,
                rejection_counts=search.rejection_counts,
                row_evaluations=search.row_evaluations,
                decision_diagnostic=search.decision_diagnostic,
                semantic_search=semantic_search,
            )

        selected = candidates[0]
        diagnostic = self._diagnostic(
            band_start=band_start,
            band_end=band_end,
            band_width=band_width,
            image_width=image_width,
            effective_chart_right_x=effective_chart_right_x,
            effective_chart_right_source=effective_chart_right_source,
            masked_pixel_count=masked_pixel_count,
            safe_top=safe_top,
            safe_bottom=safe_bottom,
            selected=selected,
            reason=None,
        )
        if semantic_ambiguity or (
            semantic_search.mode is CurrentVisualPriceSemanticSearchMode.FIXED_OVERRIDE
            and len(candidates) > 1
            and selected.score - candidates[1].score <= self._ambiguity_score_delta
        ):
            decision_diagnostic = (
                "multiple_semantic_prices"
                if semantic_ambiguity
                else "ambiguous_candidates"
            )
            extraction = CurrentVisualPriceExtraction(
                price=None,
                status=CurrentVisualPriceStatus.AMBIGUOUS_VISUAL_PRICE,
                candidate_count=len(candidates),
                selected_x=None if semantic_ambiguity else selected.x,
                selected_y=None if semantic_ambiguity else selected.y,
                confidence=None if semantic_ambiguity else selected.score,
                diagnostic=diagnostic,
            )
            trace_selected = None if semantic_ambiguity else selected
        elif selected.score < self._min_confidence:
            decision_diagnostic = "candidate_low_confidence"
            extraction = CurrentVisualPriceExtraction(
                price=None,
                status=CurrentVisualPriceStatus.LOW_CONFIDENCE,
                candidate_count=len(candidates),
                selected_x=selected.x,
                selected_y=selected.y,
                confidence=selected.score,
                diagnostic=diagnostic,
            )
            trace_selected = selected
        else:
            decision_diagnostic = "candidate_available"
            extraction = CurrentVisualPriceExtraction(
                price=CurrentVisualPrice(
                    roi_y=selected.y,
                    normalized_roi_y=1.0 - selected.y / (image_height - 1),
                    roi_width=image_width,
                    roi_height=image_height,
                    source=self._source,
                    confidence=selected.score,
                ),
                status=CurrentVisualPriceStatus.OK,
                candidate_count=len(candidates),
                selected_x=selected.x,
                selected_y=selected.y,
                confidence=selected.score,
                diagnostic=diagnostic,
            )
            trace_selected = selected
        counts = search.rejection_counts
        if semantic_search.mode is CurrentVisualPriceSemanticSearchMode.DYNAMIC:
            counts = CurrentVisualPriceRejectionCounts(
                rows_without_mask_pixels=counts.rows_without_mask_pixels,
                rows_with_mask_pixels=counts.rows_with_mask_pixels,
                rejected_by_coverage=counts.rejected_by_coverage,
                rejected_by_span=counts.rejected_by_span,
                rejected_by_right_edge_gap=counts.rejected_by_right_edge_gap,
                qualifying_rows=counts.qualifying_rows,
                candidate_groups=len(candidates),
                rejected_by_group_height=0,
                line_evidence_rows=counts.line_evidence_rows,
                rejected_by_label_support=counts.rejected_by_label_support,
            )
        return self._analysis(
            extraction=extraction,
            image_width=image_width,
            image_height=image_height,
            effective_chart_right_x=effective_chart_right_x,
            effective_chart_right_source=effective_chart_right_source,
            band_start=band_start,
            band_end=band_end,
            band_width=band_width,
            safe_top=safe_top,
            safe_bottom=safe_bottom,
            masked_pixel_count=masked_pixel_count,
            candidates=candidates,
            selected=trace_selected,
            rejection_counts=counts,
            row_evaluations=search.row_evaluations,
            decision_diagnostic=decision_diagnostic,
            semantic_search=semantic_search,
        )

    @staticmethod
    def _whole_image_rejection_counts(
        mask: np.ndarray,
    ) -> CurrentVisualPriceRejectionCounts:
        rows_with_pixels = int(np.count_nonzero(np.any(mask != 0, axis=1)))
        return CurrentVisualPriceRejectionCounts(
            rows_without_mask_pixels=mask.shape[0] - rows_with_pixels,
            rows_with_mask_pixels=rows_with_pixels,
        )

    @staticmethod
    def _candidate_qualified_row_ids(
        *,
        candidate: _Candidate,
        search: _CandidateSearch,
    ) -> tuple[int, ...]:
        return tuple(
            sorted(
                {
                    row.row_y
                    for row in search.row_evaluations
                    if candidate.row_start <= row.row_y <= candidate.row_end
                    and row.qualified
                }
            )
        )

    @staticmethod
    def _candidate_line_hypothesis_ids(
        *,
        candidate: _Candidate,
        search: _CandidateSearch,
        plan: CurrentVisualPriceSearchPlan,
    ) -> tuple[str, ...]:
        qualified_rows = tuple(
            row
            for row in search.row_evaluations
            if candidate.row_start <= row.row_y <= candidate.row_end and row.qualified
        )
        identifiers: list[str] = []
        for hypothesis in plan.line_hypotheses:
            if any(
                run.row_y == row.row_y
                and max(run.start_x, row.line_run_start_x)
                < min(run.end_x, row.line_run_end_x + 1)
                for run in hypothesis.runs
                for row in qualified_rows
            ):
                identifiers.append(hypothesis.hypothesis_id)
        return tuple(identifiers)

    @staticmethod
    def _semantic_candidate_groups(
        candidates: tuple[_QualifiedSemanticCandidate, ...],
    ) -> tuple[_SemanticCandidateGroup, ...]:
        if not candidates:
            return ()
        ordered = tuple(
            sorted(candidates, key=lambda candidate: candidate.semantic_candidate_id)
        )
        disjoint = _DisjointSet(len(ordered))
        for left_index, left in enumerate(ordered):
            left_ids = frozenset(left.line_hypothesis_ids)
            for right_index in range(left_index + 1, len(ordered)):
                right = ordered[right_index]
                shared_line_provenance = bool(
                    left_ids.intersection(right.line_hypothesis_ids)
                )
                # CurrentVisualPrice represents a vertical coordinate. Two
                # qualified detections with the same exact, non-empty raster-row
                # support therefore cannot represent distinct vertical prices,
                # even when a horizontal occlusion fragmented their provenance.
                shared_exact_raster_support = bool(left.qualified_row_ids) and (
                    left.qualified_row_ids == right.qualified_row_ids
                )
                if shared_line_provenance or shared_exact_raster_support:
                    disjoint.union(left_index, right_index)
        grouped: dict[int, list[_QualifiedSemanticCandidate]] = {}
        for index, candidate in enumerate(ordered):
            grouped.setdefault(disjoint.find(index), []).append(candidate)
        member_groups = sorted(
            (tuple(members) for members in grouped.values()),
            key=lambda members: tuple(
                member.semantic_candidate_id for member in members
            ),
        )
        result: list[_SemanticCandidateGroup] = []
        for index, members in enumerate(member_groups):
            representative_window = max(
                (member.window for member in members),
                key=lambda window: (window.end_x, window.start_x, window.window_id),
            )
            representative = min(
                (
                    member
                    for member in members
                    if member.window.window_id == representative_window.window_id
                ),
                key=lambda member: (
                    member.candidate.row_start,
                    member.candidate.row_end,
                    member.semantic_candidate_id,
                ),
            )
            result.append(
                _SemanticCandidateGroup(
                    group_id=f"semantic_price_{index:03d}",
                    members=members,
                    line_hypothesis_ids=tuple(
                        sorted(
                            {
                                line_id
                                for member in members
                                for line_id in member.line_hypothesis_ids
                            }
                        )
                    ),
                    representative=representative,
                )
            )
        return tuple(result)

    @staticmethod
    def _semantic_group_trace(
        group: _SemanticCandidateGroup,
    ) -> CurrentVisualPriceSemanticCandidateGroupTrace:
        return CurrentVisualPriceSemanticCandidateGroupTrace(
            group_id=group.group_id,
            semantic_candidate_ids=tuple(
                member.semantic_candidate_id for member in group.members
            ),
            line_hypothesis_ids=group.line_hypothesis_ids,
            window_ids=tuple(
                sorted({member.window.window_id for member in group.members})
            ),
            representative_window_id=group.representative.window.window_id,
        )

    @staticmethod
    def _analysis(
        *,
        extraction: CurrentVisualPriceExtraction,
        image_width: int,
        image_height: int,
        effective_chart_right_x: int | None,
        effective_chart_right_source: str | None,
        band_start: int | None,
        band_end: int | None,
        band_width: int | None,
        safe_top: int,
        safe_bottom: int,
        masked_pixel_count: int,
        candidates: tuple[_Candidate, ...],
        selected: _Candidate | None,
        rejection_counts: CurrentVisualPriceRejectionCounts,
        row_evaluations: tuple[CurrentVisualPriceRowEvaluationTrace, ...],
        decision_diagnostic: str,
        semantic_search: CurrentVisualPriceSemanticSearchTrace | None = None,
    ) -> CurrentVisualPriceAnalysis:
        candidate_traces = tuple(
            CurrentVisualPriceCandidateTrace(
                candidate_id=f"price_candidate_{index:03d}",
                x=candidate.x,
                y=candidate.y,
                row_start=candidate.row_start,
                row_end=candidate.row_end,
                coverage=candidate.coverage,
                span=candidate.span,
                right_edge_gap=candidate.right_edge_gap,
                score=candidate.score,
                selected=candidate is selected,
            )
            for index, candidate in enumerate(candidates)
        )
        return CurrentVisualPriceAnalysis(
            extraction=extraction,
            trace=CurrentVisualPriceDetectionTrace(
                status=extraction.status,
                image_width=image_width,
                image_height=image_height,
                effective_chart_right_x=effective_chart_right_x,
                effective_chart_right_source=effective_chart_right_source,
                band_start=band_start,
                band_end=band_end,
                band_width=band_width,
                safe_top=safe_top,
                safe_bottom=safe_bottom,
                masked_pixel_count=masked_pixel_count,
                candidates=candidate_traces,
                rejection_counts=rejection_counts,
                row_evaluations=row_evaluations,
                decision_diagnostic=decision_diagnostic,
                semantic_search=semantic_search,
            ),
        )

    def _search_candidates(
        self,
        mask: np.ndarray,
        band_start: int,
        band_end: int,
        band_width: int,
    ) -> _CandidateSearch:
        band = mask[:, band_start:band_end] != 0
        row_metrics: list[_RowMetrics] = []
        rows_without_mask_pixels = 0
        rows_with_mask_pixels = 0
        rejected_by_coverage = 0
        rejected_by_span = 0
        rejected_by_right_edge_gap = 0
        maximum_line_gap = ceil(band_width * self._max_line_gap_ratio)
        maximum_line_start_offset = ceil(band_width * self._max_line_start_offset_ratio)
        for y, row in enumerate(band):
            xs = np.flatnonzero(row)
            if xs.size == 0:
                rows_without_mask_pixels += 1
                continue
            rows_with_mask_pixels += 1
            coverage = float(xs.size / band_width)
            span = float((xs[-1] - xs[0] + 1) / band_width)
            candidate_last_x = band_start + int(xs[-1])
            right_edge_gap = int(band_end - 1 - candidate_last_x)
            if coverage < self._min_row_coverage_ratio:
                rejected_by_coverage += 1
            if span < self._min_horizontal_span_ratio:
                rejected_by_span += 1
            if right_edge_gap > self._max_right_edge_gap_px:
                rejected_by_right_edge_gap += 1
            runs = self._continuous_runs(xs)
            longest_run = max(
                runs,
                key=lambda run: (run.size, -int(run[0])),
            )
            line_run = max(
                self._supported_runs(runs, maximum_line_gap),
                key=lambda run: (
                    run.span_pixels,
                    run.continuity,
                    -run.start,
                ),
            )
            line_run_span_ratio = line_run.span_pixels / band_width
            line_rejections: list[CurrentVisualPriceRowRejectionReason] = []
            if line_run_span_ratio < self._min_line_run_ratio:
                line_rejections.append(
                    CurrentVisualPriceRowRejectionReason.LINE_RUN_TOO_SHORT
                )
            if line_run.continuity < self._min_line_continuity_ratio:
                line_rejections.append(
                    CurrentVisualPriceRowRejectionReason.LINE_CONTINUITY_TOO_LOW
                )
            if line_run.start > maximum_line_start_offset:
                line_rejections.append(
                    CurrentVisualPriceRowRejectionReason.LINE_STARTS_TOO_LATE
                )
            row_metrics.append(
                _RowMetrics(
                    y=y,
                    xs=xs,
                    coverage=coverage,
                    span=span,
                    right_edge_gap=right_edge_gap,
                    longest_run=longest_run,
                    component_count=len(runs),
                    line_run=line_run,
                    line_run_span_ratio=line_run_span_ratio,
                    line_evidence=not line_rejections,
                    line_rejection_reasons=tuple(line_rejections),
                )
            )

        line_row_ids = frozenset(
            metrics.y for metrics in row_metrics if metrics.line_evidence
        )
        qualifying: list[tuple[_RowMetrics, CurrentVisualPriceLabelSupportTrace]] = []
        row_evaluations: list[CurrentVisualPriceRowEvaluationTrace] = []
        rejected_by_label_support = 0
        for metrics in row_metrics:
            label_trace = None
            label_support = False
            rejection_reasons = list(metrics.line_rejection_reasons)
            if metrics.line_evidence:
                label_trace = self._label_support_trace(
                    band=band,
                    row_y=metrics.y,
                    line_row_ids=line_row_ids,
                    band_start=band_start,
                    band_end=band_end,
                    band_width=band_width,
                )
                label_support = label_trace.supported
                if not label_support:
                    rejected_by_label_support += 1
                    rejection_reasons.append(
                        CurrentVisualPriceRowRejectionReason.LABEL_SUPPORT_MISSING
                    )
            qualified = metrics.line_evidence and label_support
            if qualified:
                assert label_trace is not None
                qualifying.append((metrics, label_trace))
            row_evaluations.append(
                CurrentVisualPriceRowEvaluationTrace(
                    row_y=metrics.y,
                    masked_pixels=int(metrics.xs.size),
                    coverage=metrics.coverage,
                    span=metrics.span,
                    left_x=band_start + int(metrics.xs[0]),
                    right_x=band_start + int(metrics.xs[-1]),
                    right_edge_gap=metrics.right_edge_gap,
                    longest_run_pixels=int(metrics.longest_run.size),
                    longest_run_ratio=float(metrics.longest_run.size / band_width),
                    longest_run_start_x=(band_start + int(metrics.longest_run[0])),
                    longest_run_end_x=(band_start + int(metrics.longest_run[-1])),
                    component_count=metrics.component_count,
                    line_run_pixels=metrics.line_run.masked_pixels,
                    line_run_span_pixels=metrics.line_run.span_pixels,
                    line_run_span_ratio=metrics.line_run_span_ratio,
                    line_run_start_x=band_start + metrics.line_run.start,
                    line_run_end_x=band_start + metrics.line_run.end,
                    line_run_continuity=metrics.line_run.continuity,
                    pass_coverage=(metrics.coverage >= self._min_row_coverage_ratio),
                    pass_span=(metrics.span >= self._min_horizontal_span_ratio),
                    pass_edge=(metrics.right_edge_gap <= self._max_right_edge_gap_px),
                    line_evidence=metrics.line_evidence,
                    label_support=label_support,
                    qualified=qualified,
                    rejection_reasons=tuple(rejection_reasons),
                    label_support_trace=label_trace,
                )
            )

        groups: list[list[tuple[_RowMetrics, CurrentVisualPriceLabelSupportTrace]]] = []
        for row in qualifying:
            if groups and row[0].y - groups[-1][-1][0].y <= self._max_row_gap_px + 1:
                groups[-1].append(row)
            else:
                groups.append([row])

        candidates: list[_Candidate] = []
        rejected_by_group_height = 0
        for group in groups:
            row_start = group[0][0].y
            row_end = group[-1][0].y
            if row_end - row_start + 1 > self._max_candidate_height_px:
                rejected_by_group_height += 1
                continue
            weights = np.array(
                [row[0].xs.size for row in group],
                dtype=np.float64,
            )
            ys = np.array([row[0].y for row in group], dtype=np.float64)
            x_centers = np.array(
                [(row[0].xs[0] + row[0].xs[-1]) / 2 + band_start for row in group],
                dtype=np.float64,
            )
            coverage = float(
                np.average(
                    [row[0].coverage for row in group],
                    weights=weights,
                )
            )
            span = float(
                np.average(
                    [row[0].span for row in group],
                    weights=weights,
                )
            )
            right_edge_gap = min(row[0].right_edge_gap for row in group)
            line_span_score = float(
                np.average(
                    [row[0].line_run_span_ratio for row in group],
                    weights=weights,
                )
            )
            line_continuity_score = float(
                np.average(
                    [row[0].line_run.continuity for row in group],
                    weights=weights,
                )
            )
            label_support_score = float(
                np.average(
                    [
                        (row[1].support_row_ratio + row[1].support_density) / 2.0
                        for row in group
                    ],
                    weights=weights,
                )
            )
            score = min(
                1.0,
                _LINE_SPAN_SCORE_WEIGHT * line_span_score
                + _LINE_CONTINUITY_SCORE_WEIGHT * line_continuity_score
                + _LABEL_SUPPORT_SCORE_WEIGHT * label_support_score,
            )
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
        if not row_metrics:
            decision_diagnostic = "no_pixels_in_band"
        elif not line_row_ids:
            decision_diagnostic = "no_line_rows"
        elif not qualifying:
            decision_diagnostic = "line_rows_without_label_support"
        elif groups and not candidates:
            decision_diagnostic = "candidate_groups_rejected"
        else:
            decision_diagnostic = "candidate_available"
        return _CandidateSearch(
            candidates=tuple(candidates),
            rejection_counts=CurrentVisualPriceRejectionCounts(
                rows_without_mask_pixels=rows_without_mask_pixels,
                rows_with_mask_pixels=rows_with_mask_pixels,
                rejected_by_coverage=rejected_by_coverage,
                rejected_by_span=rejected_by_span,
                rejected_by_right_edge_gap=rejected_by_right_edge_gap,
                qualifying_rows=len(qualifying),
                candidate_groups=len(groups),
                rejected_by_group_height=rejected_by_group_height,
                line_evidence_rows=len(line_row_ids),
                rejected_by_label_support=rejected_by_label_support,
            ),
            row_evaluations=tuple(row_evaluations),
            decision_diagnostic=decision_diagnostic,
        )

    @staticmethod
    def _continuous_runs(xs: np.ndarray) -> tuple[np.ndarray, ...]:
        split_points = np.flatnonzero(np.diff(xs) > 1) + 1
        return tuple(np.split(xs, split_points))

    @staticmethod
    def _supported_runs(
        runs: tuple[np.ndarray, ...],
        maximum_gap: int,
    ) -> tuple[_SupportedRun, ...]:
        supported: list[_SupportedRun] = []
        start = int(runs[0][0])
        end = int(runs[0][-1])
        masked_pixels = int(runs[0].size)
        for run in runs[1:]:
            run_start = int(run[0])
            run_end = int(run[-1])
            if run_start - end - 1 <= maximum_gap:
                end = run_end
                masked_pixels += int(run.size)
                continue
            supported.append(
                _SupportedRun(
                    start=start,
                    end=end,
                    masked_pixels=masked_pixels,
                )
            )
            start = run_start
            end = run_end
            masked_pixels = int(run.size)
        supported.append(
            _SupportedRun(
                start=start,
                end=end,
                masked_pixels=masked_pixels,
            )
        )
        return tuple(supported)

    def _label_support_trace(
        self,
        *,
        band: np.ndarray,
        row_y: int,
        line_row_ids: frozenset[int],
        band_start: int,
        band_end: int,
        band_width: int,
    ) -> CurrentVisualPriceLabelSupportTrace:
        vertical_radius = max(
            1,
            ceil(band.shape[0] * self._label_vertical_radius_ratio),
        )
        window_start = max(0, row_y - vertical_radius)
        window_end = min(band.shape[0], row_y + vertical_radius + 1)
        label_zone_width = max(1, ceil(band_width * self._label_zone_ratio))
        label_zone_start = band_width - label_zone_width
        support_mask = band[
            window_start:window_end,
            label_zone_start:band_width,
        ].copy()
        excluded_line_rows = tuple(
            y for y in line_row_ids if window_start <= y < window_end
        )
        for line_y in excluded_line_rows:
            support_mask[line_y - window_start, :] = False
        evaluated_row_count = support_mask.shape[0] - len(excluded_line_rows)
        support_pixels = int(np.count_nonzero(support_mask))
        support_row_count = int(np.count_nonzero(np.any(support_mask, axis=1)))
        support_row_ratio = (
            support_row_count / evaluated_row_count if evaluated_row_count else 0.0
        )
        support_area = evaluated_row_count * label_zone_width
        support_density = support_pixels / support_area if support_area else 0.0
        supported = (
            support_row_ratio >= self._min_label_support_row_ratio
            and support_density >= self._min_label_support_density_ratio
        )
        if support_pixels == 0:
            diagnostic = "no_right_side_support"
        elif support_row_ratio < self._min_label_support_row_ratio:
            diagnostic = "insufficient_support_rows"
        elif support_density < self._min_label_support_density_ratio:
            diagnostic = "insufficient_support_density"
        else:
            diagnostic = "label_support_available"
        return CurrentVisualPriceLabelSupportTrace(
            window_start_y=window_start,
            window_end_y=window_end,
            zone_start_x=band_start + label_zone_start,
            zone_end_x=band_end,
            support_pixels=support_pixels,
            support_row_count=support_row_count,
            evaluated_row_count=evaluated_row_count,
            support_row_ratio=float(support_row_ratio),
            support_density=float(support_density),
            supported=supported,
            diagnostic=diagnostic,
        )

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
