from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from math import ceil

import cv2
import numpy as np

from pocket_option_analyzer.vision.models.current_visual_price_search import (
    CurrentVisualPriceLabelComponent,
    CurrentVisualPriceLineHypothesis,
    CurrentVisualPriceLineRun,
    CurrentVisualPriceSearchConstraints,
    CurrentVisualPriceSearchPlan,
    CurrentVisualPriceSearchPlanReason,
    CurrentVisualPriceSearchPlanStatus,
    CurrentVisualPriceSearchWindow,
    CurrentVisualPriceSearchWindowOrigin,
)


@dataclass(frozen=True, slots=True)
class _ProposedWindow:
    start_x: int
    end_x: int
    line_hypothesis_id: str
    label_component_id: str


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


class PocketOptionCurrentVisualPriceSearchWindowResolver:
    """Propone ventanas a partir de pares globales de línea y label.

    El resolver sólo usa geometría necesaria. Los gates productivos completos
    se ejecutan después, una vez por ventana, en el extractor.
    """

    def __init__(self, *, max_unique_windows: int = 32) -> None:
        if (
            not isinstance(max_unique_windows, int)
            or isinstance(max_unique_windows, bool)
            or max_unique_windows < 1
        ):
            raise ValueError("max_unique_windows debe ser un entero positivo.")
        self._max_unique_windows = max_unique_windows

    def resolve(
        self,
        *,
        mask: np.ndarray,
        constraints: CurrentVisualPriceSearchConstraints,
    ) -> CurrentVisualPriceSearchPlan:
        self._validate_mask(mask, constraints)
        effective_constraints = CurrentVisualPriceSearchConstraints(
            image_width=constraints.image_width,
            image_height=constraints.image_height,
            right_band_ratio=constraints.right_band_ratio,
            max_line_gap_ratio=constraints.max_line_gap_ratio,
            max_line_start_offset_ratio=constraints.max_line_start_offset_ratio,
            min_line_run_ratio=constraints.min_line_run_ratio,
            label_zone_ratio=constraints.label_zone_ratio,
            label_vertical_radius_ratio=constraints.label_vertical_radius_ratio,
            max_row_gap_px=constraints.max_row_gap_px,
            max_candidate_height_px=constraints.max_candidate_height_px,
            max_unique_windows=self._max_unique_windows,
        )
        if not np.any(mask):
            return self._unavailable(
                effective_constraints,
                CurrentVisualPriceSearchPlanReason.NO_MASK_PIXELS,
            )

        runs = tuple(
            run
            for run in self._global_runs(mask, effective_constraints)
            if self._could_be_line_run(run, effective_constraints)
        )
        hypotheses = tuple(
            hypothesis
            for hypothesis in self._line_hypotheses(runs, effective_constraints)
            if self._has_admissible_height(hypothesis, effective_constraints)
        )
        if not hypotheses:
            return self._unavailable(
                effective_constraints,
                CurrentVisualPriceSearchPlanReason.NO_HORIZONTAL_LINE_HYPOTHESES,
            )

        residual = mask.copy()
        for hypothesis in hypotheses:
            for run in hypothesis.runs:
                residual[run.row_y, run.start_x : run.end_x] = 0
        components = self._label_components(residual)
        if not components:
            return CurrentVisualPriceSearchPlan(
                status=CurrentVisualPriceSearchPlanStatus.UNAVAILABLE,
                reason=(
                    CurrentVisualPriceSearchPlanReason.NO_LABEL_COMPONENT_HYPOTHESES
                ),
                constraints=effective_constraints,
                windows=(),
                line_hypotheses=hypotheses,
                total_proposed_window_count=0,
            )

        proposed: list[_ProposedWindow] = []
        for hypothesis in hypotheses:
            line_edges = self._admissible_line_edges(
                hypothesis,
                effective_constraints,
            )
            for component in components:
                edge = self._canonical_pair_edge(
                    hypothesis=hypothesis,
                    component=component,
                    admissible_line_edges=line_edges,
                    constraints=effective_constraints,
                )
                if edge is None:
                    continue
                band_width = max(
                    1,
                    ceil(edge * effective_constraints.right_band_ratio),
                )
                proposed.append(
                    _ProposedWindow(
                        start_x=edge - band_width,
                        end_x=edge,
                        line_hypothesis_id=hypothesis.hypothesis_id,
                        label_component_id=component.component_id,
                    )
                )

        if not proposed:
            return CurrentVisualPriceSearchPlan(
                status=CurrentVisualPriceSearchPlanStatus.UNAVAILABLE,
                reason=(
                    CurrentVisualPriceSearchPlanReason.NO_COMPATIBLE_LINE_LABEL_PAIRS
                ),
                constraints=effective_constraints,
                windows=(),
                line_hypotheses=hypotheses,
                label_components=components,
                total_proposed_window_count=0,
            )

        windows = self._deduplicate_windows(proposed)
        if len(windows) > effective_constraints.max_unique_windows:
            descriptors = tuple(
                f"{window.start_x}:{window.end_x}:"
                f"{','.join(window.line_hypothesis_ids)}:"
                f"{','.join(window.label_component_ids)}"
                for window in windows
            )
            digest = sha256("\n".join(descriptors).encode("utf-8")).hexdigest()
            return CurrentVisualPriceSearchPlan(
                status=CurrentVisualPriceSearchPlanStatus.UNAVAILABLE,
                reason=CurrentVisualPriceSearchPlanReason.WINDOW_LIMIT_EXCEEDED,
                constraints=effective_constraints,
                windows=windows[: effective_constraints.max_unique_windows],
                line_hypotheses=hypotheses,
                label_components=components,
                total_proposed_window_count=len(windows),
                full_window_set_sha256=digest,
            )
        return CurrentVisualPriceSearchPlan(
            status=CurrentVisualPriceSearchPlanStatus.AVAILABLE,
            reason=CurrentVisualPriceSearchPlanReason.SEMANTIC_WINDOWS_AVAILABLE,
            constraints=effective_constraints,
            windows=windows,
            line_hypotheses=hypotheses,
            label_components=components,
            total_proposed_window_count=len(windows),
        )

    @staticmethod
    def _validate_mask(
        mask: np.ndarray,
        constraints: CurrentVisualPriceSearchConstraints,
    ) -> None:
        if (
            not isinstance(mask, np.ndarray)
            or mask.dtype != np.uint8
            or mask.ndim != 2
            or mask.shape != (constraints.image_height, constraints.image_width)
        ):
            raise ValueError(
                "mask debe ser una matriz uint8 2D con la geometría declarada."
            )

    @staticmethod
    def _unavailable(
        constraints: CurrentVisualPriceSearchConstraints,
        reason: CurrentVisualPriceSearchPlanReason,
    ) -> CurrentVisualPriceSearchPlan:
        return CurrentVisualPriceSearchPlan(
            status=CurrentVisualPriceSearchPlanStatus.UNAVAILABLE,
            reason=reason,
            constraints=constraints,
            windows=(),
            total_proposed_window_count=0,
        )

    @staticmethod
    def _global_runs(
        mask: np.ndarray,
        constraints: CurrentVisualPriceSearchConstraints,
    ) -> tuple[CurrentVisualPriceLineRun, ...]:
        maximum_gap = ceil(
            constraints.image_width
            * constraints.right_band_ratio
            * constraints.max_line_gap_ratio
        )
        result: list[CurrentVisualPriceLineRun] = []
        for row_y in range(mask.shape[0]):
            xs = np.flatnonzero(mask[row_y])
            if xs.size == 0:
                continue
            split_points = np.flatnonzero(np.diff(xs) > 1) + 1
            raw_runs = tuple(np.split(xs, split_points))
            start = int(raw_runs[0][0])
            end = int(raw_runs[0][-1]) + 1
            for raw_run in raw_runs[1:]:
                run_start = int(raw_run[0])
                run_end = int(raw_run[-1]) + 1
                if run_start - end <= maximum_gap:
                    end = run_end
                    continue
                result.append(
                    CurrentVisualPriceLineRun(
                        row_y=row_y,
                        start_x=start,
                        end_x=end,
                    )
                )
                start = run_start
                end = run_end
            result.append(
                CurrentVisualPriceLineRun(
                    row_y=row_y,
                    start_x=start,
                    end_x=end,
                )
            )
        return tuple(
            sorted(result, key=lambda run: (run.row_y, run.start_x, run.end_x))
        )

    @staticmethod
    def _line_hypotheses(
        runs: tuple[CurrentVisualPriceLineRun, ...],
        constraints: CurrentVisualPriceSearchConstraints,
    ) -> tuple[CurrentVisualPriceLineHypothesis, ...]:
        if not runs:
            return ()
        disjoint = _DisjointSet(len(runs))
        for left_index, left in enumerate(runs):
            for right_index in range(left_index + 1, len(runs)):
                right = runs[right_index]
                row_distance = right.row_y - left.row_y
                if row_distance > constraints.max_row_gap_px + 1:
                    break
                overlaps = max(left.start_x, right.start_x) < min(
                    left.end_x,
                    right.end_x,
                )
                if overlaps:
                    disjoint.union(left_index, right_index)
        grouped: dict[int, list[CurrentVisualPriceLineRun]] = {}
        for index, run in enumerate(runs):
            grouped.setdefault(disjoint.find(index), []).append(run)
        ordered = sorted(
            (tuple(group) for group in grouped.values()),
            key=lambda group: (
                group[0].row_y,
                min(run.start_x for run in group),
                max(run.end_x for run in group),
                len(group),
            ),
        )
        return tuple(
            CurrentVisualPriceLineHypothesis(
                hypothesis_id=f"line_hypothesis_{index:03d}",
                runs=tuple(sorted(group, key=lambda run: (run.row_y, run.start_x))),
            )
            for index, group in enumerate(ordered)
        )

    @staticmethod
    def _could_be_line_run(
        run: CurrentVisualPriceLineRun,
        constraints: CurrentVisualPriceSearchConstraints,
    ) -> bool:
        minimum_band_width = max(
            1,
            ceil(run.end_x * constraints.right_band_ratio),
        )
        return (run.end_x - run.start_x) / minimum_band_width >= (
            constraints.min_line_run_ratio
        )

    @staticmethod
    def _has_admissible_height(
        hypothesis: CurrentVisualPriceLineHypothesis,
        constraints: CurrentVisualPriceSearchConstraints,
    ) -> bool:
        top = min(run.row_y for run in hypothesis.runs)
        bottom = max(run.row_y for run in hypothesis.runs) + 1
        return bottom - top <= constraints.max_candidate_height_px

    @staticmethod
    def _admissible_line_edges(
        hypothesis: CurrentVisualPriceLineHypothesis,
        constraints: CurrentVisualPriceSearchConstraints,
    ) -> tuple[int, ...]:
        minimum_edge = max(1, min(run.end_x for run in hypothesis.runs))
        edges = np.arange(
            minimum_edge,
            constraints.image_width + 1,
            dtype=np.int32,
        )
        if edges.size == 0:
            return ()
        band_widths = np.ceil(
            edges.astype(np.float64) * constraints.right_band_ratio
        ).astype(np.int32)
        band_widths = np.maximum(1, band_widths)
        band_starts = edges - band_widths
        maximum_start_offsets = np.ceil(
            band_widths.astype(np.float64) * constraints.max_line_start_offset_ratio
        ).astype(np.int32)
        valid = np.zeros(edges.shape, dtype=np.bool_)
        for run in hypothesis.runs:
            overlap_starts = np.maximum(run.start_x, band_starts)
            overlap_ends = np.minimum(run.end_x, edges)
            overlaps = np.maximum(0, overlap_ends - overlap_starts)
            start_offsets = np.maximum(0, run.start_x - band_starts)
            valid |= (overlaps / band_widths >= constraints.min_line_run_ratio) & (
                start_offsets <= maximum_start_offsets
            )
        return tuple(int(edge) for edge in edges[valid])

    @staticmethod
    def _label_components(
        residual: np.ndarray,
    ) -> tuple[CurrentVisualPriceLabelComponent, ...]:
        binary = np.where(residual != 0, 1, 0).astype(np.uint8, copy=False)
        count, _, stats, _ = cv2.connectedComponentsWithStats(
            binary,
            connectivity=8,
        )
        geometries = sorted(
            (
                int(stats[index, cv2.CC_STAT_LEFT]),
                int(stats[index, cv2.CC_STAT_TOP]),
                int(stats[index, cv2.CC_STAT_WIDTH]),
                int(stats[index, cv2.CC_STAT_HEIGHT]),
                int(stats[index, cv2.CC_STAT_AREA]),
            )
            for index in range(1, count)
            if int(stats[index, cv2.CC_STAT_AREA]) > 0
        )
        return tuple(
            CurrentVisualPriceLabelComponent(
                component_id=f"label_component_{index:03d}",
                x=x,
                y=y,
                width=width,
                height=height,
                area=area,
            )
            for index, (x, y, width, height, area) in enumerate(geometries)
        )

    @staticmethod
    def _canonical_pair_edge(
        *,
        hypothesis: CurrentVisualPriceLineHypothesis,
        component: CurrentVisualPriceLabelComponent,
        admissible_line_edges: tuple[int, ...],
        constraints: CurrentVisualPriceSearchConstraints,
    ) -> int | None:
        line_top = min(run.row_y for run in hypothesis.runs)
        line_bottom = max(run.row_y for run in hypothesis.runs) + 1
        vertical_distance = max(
            line_top - component.end_y,
            component.y - line_bottom,
            0,
        )
        vertical_radius = max(
            1,
            ceil(constraints.image_height * constraints.label_vertical_radius_ratio),
        )
        if vertical_distance > vertical_radius:
            return None
        line_right = max(run.end_x for run in hypothesis.runs)
        if component.end_x < line_right:
            return None
        compatible: list[int] = []
        for edge in admissible_line_edges:
            band_width = max(1, ceil(edge * constraints.right_band_ratio))
            label_zone_width = max(
                1,
                ceil(band_width * constraints.label_zone_ratio),
            )
            zone_start = edge - label_zone_width
            if not (component.x < edge <= component.end_x):
                continue
            if max(component.x, zone_start) >= min(component.end_x, edge):
                continue
            compatible.append(edge)
        return max(compatible) if compatible else None

    @staticmethod
    def _deduplicate_windows(
        proposed: list[_ProposedWindow],
    ) -> tuple[CurrentVisualPriceSearchWindow, ...]:
        grouped: dict[tuple[int, int], tuple[set[str], set[str]]] = {}
        for item in proposed:
            line_ids, label_ids = grouped.setdefault(
                (item.start_x, item.end_x),
                (set(), set()),
            )
            line_ids.add(item.line_hypothesis_id)
            label_ids.add(item.label_component_id)
        ordered = sorted(grouped.items(), key=lambda item: item[0])
        return tuple(
            CurrentVisualPriceSearchWindow(
                window_id=f"search_window_{index:03d}",
                start_x=geometry[0],
                end_x=geometry[1],
                origin=(CurrentVisualPriceSearchWindowOrigin.SEMANTIC_LINE_LABEL_PAIR),
                line_hypothesis_ids=tuple(sorted(provenance[0])),
                label_component_ids=tuple(sorted(provenance[1])),
            )
            for index, (geometry, provenance) in enumerate(ordered)
        )
