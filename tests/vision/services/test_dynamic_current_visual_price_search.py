from __future__ import annotations

from dataclasses import replace
from math import ceil

import numpy as np
import pytest

from pocket_option_analyzer.vision.models import (
    CurrentVisualPriceLineHypothesis,
    CurrentVisualPriceLineRun,
    CurrentVisualPriceSearchConstraints,
    CurrentVisualPriceSearchPlan,
    CurrentVisualPriceSearchPlanReason,
    CurrentVisualPriceSearchPlanStatus,
    CurrentVisualPriceSearchWindow,
    CurrentVisualPriceSearchWindowOrigin,
    CurrentVisualPriceSemanticResolutionReason,
    CurrentVisualPriceSemanticResolutionStatus,
    CurrentVisualPriceSemanticSearchMode,
    CurrentVisualPriceStatus,
)
from pocket_option_analyzer.vision.services import (
    CurrentVisualPriceSearchWindowResolver,
    PocketOptionCurrentVisualPriceExtractor,
    PocketOptionCurrentVisualPriceSearchWindowResolver,
)
from pocket_option_analyzer.vision.services import (
    pocket_option_current_visual_price_extractor as extractor_module,
)

_Candidate = extractor_module._Candidate
_QualifiedSemanticCandidate = extractor_module._QualifiedSemanticCandidate


class _FixedMaskBuilder:
    def __init__(self, mask: np.ndarray) -> None:
        self.mask = mask
        self.calls = 0

    def build(self, frame: np.ndarray) -> np.ndarray:
        self.calls += 1
        assert frame.shape[:2] == self.mask.shape
        return self.mask.copy()


class _ReverseWindowResolver:
    def __init__(self) -> None:
        self._delegate = PocketOptionCurrentVisualPriceSearchWindowResolver()

    def resolve(
        self,
        *,
        mask: np.ndarray,
        constraints: CurrentVisualPriceSearchConstraints,
    ) -> CurrentVisualPriceSearchPlan:
        plan = self._delegate.resolve(mask=mask, constraints=constraints)
        return replace(plan, windows=tuple(reversed(plan.windows)))


class _UnavailableResolver:
    def resolve(
        self,
        *,
        mask: np.ndarray,
        constraints: CurrentVisualPriceSearchConstraints,
    ) -> CurrentVisualPriceSearchPlan:
        return CurrentVisualPriceSearchPlan(
            status=CurrentVisualPriceSearchPlanStatus.UNAVAILABLE,
            reason=CurrentVisualPriceSearchPlanReason.WINDOW_LIMIT_EXCEEDED,
            constraints=replace(constraints, max_unique_windows=1),
            windows=(),
            total_proposed_window_count=2,
            full_window_set_sha256="0" * 64,
        )


class _UnmappedCandidateResolver:
    def resolve(
        self,
        *,
        mask: np.ndarray,
        constraints: CurrentVisualPriceSearchConstraints,
    ) -> CurrentVisualPriceSearchPlan:
        return CurrentVisualPriceSearchPlan(
            status=CurrentVisualPriceSearchPlanStatus.AVAILABLE,
            reason=CurrentVisualPriceSearchPlanReason.SEMANTIC_WINDOWS_AVAILABLE,
            constraints=constraints,
            windows=(
                CurrentVisualPriceSearchWindow(
                    window_id="search_window_000",
                    start_x=80,
                    end_x=100,
                    origin=(
                        CurrentVisualPriceSearchWindowOrigin.SEMANTIC_LINE_LABEL_PAIR
                    ),
                    line_hypothesis_ids=("line_hypothesis_000",),
                    label_component_ids=("label_component_000",),
                ),
            ),
            line_hypotheses=(
                CurrentVisualPriceLineHypothesis(
                    hypothesis_id="line_hypothesis_000",
                    runs=(
                        CurrentVisualPriceLineRun(
                            row_y=10,
                            start_x=80,
                            end_x=95,
                        ),
                    ),
                ),
            ),
            total_proposed_window_count=1,
        )


class _RecordingResolver:
    def __init__(self) -> None:
        self.mask: np.ndarray | None = None
        self._delegate = PocketOptionCurrentVisualPriceSearchWindowResolver()

    def resolve(
        self,
        *,
        mask: np.ndarray,
        constraints: CurrentVisualPriceSearchConstraints,
    ) -> CurrentVisualPriceSearchPlan:
        self.mask = mask
        return self._delegate.resolve(mask=mask, constraints=constraints)


class _RecordingExtractor(PocketOptionCurrentVisualPriceExtractor):
    qualification_masks: list[np.ndarray]

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self.qualification_masks = []

    def _search_candidates(
        self,
        mask: np.ndarray,
        band_start: int,
        band_end: int,
        band_width: int,
    ):
        self.qualification_masks.append(mask)
        return super()._search_candidates(mask, band_start, band_end, band_width)


class _FragmentedLineResolver:
    def __init__(self, *, gap: int) -> None:
        self._gap = gap

    def resolve(
        self,
        *,
        mask: np.ndarray,
        constraints: CurrentVisualPriceSearchConstraints,
    ) -> CurrentVisualPriceSearchPlan:
        if mask.shape[1] == 1154:
            left_start, left_end = 500, 600
            right_start, right_end = left_end + self._gap, 1000
            windows = ((500, 620), (840, 1062))
        else:
            left_start, left_end = 437, 523
            right_start, right_end = left_end + self._gap, 757
            windows = ((437, 547), (644, 805))
        return CurrentVisualPriceSearchPlan(
            status=CurrentVisualPriceSearchPlanStatus.AVAILABLE,
            reason=CurrentVisualPriceSearchPlanReason.SEMANTIC_WINDOWS_AVAILABLE,
            constraints=constraints,
            windows=tuple(
                CurrentVisualPriceSearchWindow(
                    window_id=f"search_window_{index:03d}",
                    start_x=start,
                    end_x=end,
                    origin=(
                        CurrentVisualPriceSearchWindowOrigin.SEMANTIC_LINE_LABEL_PAIR
                    ),
                    line_hypothesis_ids=(f"line_hypothesis_{index:03d}",),
                    label_component_ids=(f"label_component_{index:03d}",),
                )
                for index, (start, end) in enumerate(windows)
            ),
            line_hypotheses=(
                CurrentVisualPriceLineHypothesis(
                    hypothesis_id="line_hypothesis_000",
                    runs=(
                        CurrentVisualPriceLineRun(
                            row_y=mask.shape[0] // 2,
                            start_x=left_start,
                            end_x=left_end,
                        ),
                    ),
                ),
                CurrentVisualPriceLineHypothesis(
                    hypothesis_id="line_hypothesis_001",
                    runs=(
                        CurrentVisualPriceLineRun(
                            row_y=mask.shape[0] // 2,
                            start_x=right_start,
                            end_x=right_end,
                        ),
                    ),
                ),
            ),
            total_proposed_window_count=2,
        )


def _marker(
    mask: np.ndarray,
    *,
    y: int,
    line_start: int,
    label_start: int,
    semantic_edge: int,
    radius: int | None = None,
) -> None:
    vertical_radius = max(1, ceil(mask.shape[0] * 0.025)) if radius is None else radius
    mask[y, line_start:semantic_edge] = 255
    mask[
        max(0, y - vertical_radius) : y,
        label_start:semantic_edge,
    ] = 255
    mask[
        y + 1 : min(mask.shape[0], y + vertical_radius + 1),
        label_start:semantic_edge,
    ] = 255


def _analyze(
    mask: np.ndarray,
    *,
    resolver: CurrentVisualPriceSearchWindowResolver | None = None,
    effective_chart_right_x: int | None = None,
):
    builder = _FixedMaskBuilder(mask)
    extractor = PocketOptionCurrentVisualPriceExtractor(
        mask_builder=builder,
        search_window_resolver=resolver,
        effective_chart_right_x=effective_chart_right_x,
    )
    image = np.zeros((*mask.shape, 3), dtype=np.uint8)
    return extractor.extract_with_trace(image), builder


def _fragmented_marker_mask(*, height: int, width: int, gap: int) -> np.ndarray:
    mask = np.zeros((height, width), dtype=np.uint8)
    y = height // 2
    if width == 1154:
        left_line = (500, 600)
        left_label = (600, 620)
        right_line = (600 + gap, 1000)
        right_label = (1000, 1062)
    else:
        left_line = (437, 523)
        left_label = (523, 547)
        right_line = (523 + gap, 757)
        right_label = (757, 805)
    for line_start, line_end in (left_line, right_line):
        mask[y, line_start:line_end] = 255
    for label_start, label_end in (left_label, right_label):
        mask[y - 6 : y, label_start:label_end] = 255
        mask[y + 1 : y + 7, label_start:label_end] = 255
    return mask


def _semantic_candidate(
    candidate_id: str,
    *,
    row_ids: tuple[int, ...],
    line_ids: tuple[str, ...],
    y: float | None = None,
    window_start: int = 0,
    window_end: int = 100,
    score: float = 0.5,
    label_id: str = "label_component_000",
) -> _QualifiedSemanticCandidate:
    candidate_y = float(row_ids[0] if row_ids else 0) if y is None else y
    row_start = min(row_ids, default=int(candidate_y))
    row_end = max(row_ids, default=int(candidate_y))
    return _QualifiedSemanticCandidate(
        semantic_candidate_id=candidate_id,
        candidate=_Candidate(
            y=candidate_y,
            x=float((window_start + window_end) / 2),
            score=score,
            row_start=row_start,
            row_end=row_end,
            coverage=1.0,
            span=1.0,
            right_edge_gap=0,
        ),
        window=CurrentVisualPriceSearchWindow(
            window_id=f"window_{candidate_id}",
            start_x=window_start,
            end_x=window_end,
            origin=CurrentVisualPriceSearchWindowOrigin.SEMANTIC_LINE_LABEL_PAIR,
            line_hypothesis_ids=line_ids,
            label_component_ids=(label_id,),
        ),
        line_hypothesis_ids=line_ids,
        qualified_row_ids=row_ids,
    )


@pytest.mark.parametrize(
    ("width", "height", "line_start", "label_start", "edge", "y"),
    [
        (1161, 800, 849, 1008, 1062, 400),
        (1180, 788, 658, 1022, 1093, 265),
        (1663, 788, 1092, 1582, 1652, 340),
        (1652, 753, 1085, 1540, 1610, 242),
        (1493, 706, 1081, 1384, 1455, 142),
        (1376, 653, 873, 1249, 1320, 312),
    ],
)
def test_dynamic_geometry_recovers_marker_across_resized_rois(
    width: int,
    height: int,
    line_start: int,
    label_start: int,
    edge: int,
    y: int,
) -> None:
    mask = np.zeros((height, width), dtype=np.uint8)
    _marker(
        mask,
        y=y,
        line_start=line_start,
        label_start=label_start,
        semantic_edge=edge,
    )

    analysis, builder = _analyze(mask)

    assert analysis.extraction.status is CurrentVisualPriceStatus.OK
    assert analysis.extraction.price is not None
    assert analysis.extraction.price.roi_y == float(y)
    assert analysis.extraction.price.normalized_roi_y == pytest.approx(
        1.0 - y / (height - 1)
    )
    assert analysis.trace.effective_chart_right_source == "semantic_resolver"
    assert analysis.trace.effective_chart_right_x == edge
    assert analysis.trace.semantic_search is not None
    assert analysis.trace.semantic_search.mode is (
        CurrentVisualPriceSemanticSearchMode.DYNAMIC
    )
    assert builder.calls == 1


def test_f523_equivalent_is_not_simple_proportional_1062_scaling() -> None:
    mask = np.zeros((788, 1180), dtype=np.uint8)
    _marker(
        mask,
        y=265,
        line_start=658,
        label_start=1022,
        semantic_edge=1093,
    )

    analysis, _ = _analyze(mask)

    proportional_edge = round(1062 * 1180 / 1161)
    assert analysis.extraction.status is CurrentVisualPriceStatus.OK
    assert analysis.trace.effective_chart_right_x == 1093
    assert analysis.trace.effective_chart_right_x != proportional_edge


def test_nominal_dynamic_result_matches_equivalent_fixed_override() -> None:
    mask = np.zeros((800, 1161), dtype=np.uint8)
    _marker(
        mask,
        y=400,
        line_start=849,
        label_start=1008,
        semantic_edge=1062,
    )

    dynamic, _ = _analyze(mask)
    fixed, _ = _analyze(mask, effective_chart_right_x=1062)

    assert (
        dynamic.extraction.status
        is fixed.extraction.status
        is (CurrentVisualPriceStatus.OK)
    )
    assert dynamic.extraction.price is not None
    assert fixed.extraction.price is not None
    assert dynamic.extraction.price.roi_y == fixed.extraction.price.roi_y
    assert (
        dynamic.extraction.price.normalized_roi_y
        == fixed.extraction.price.normalized_roi_y
    )


def test_same_price_under_multiple_windows_deduplicates_transitively() -> None:
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[50, 79:95] = 255
    mask[47:50, 95:100] = 255
    mask[51:54, 93:98] = 255

    analysis, _ = _analyze(mask)

    trace = analysis.trace.semantic_search
    assert analysis.extraction.status is CurrentVisualPriceStatus.OK
    assert analysis.extraction.candidate_count == 1
    assert trace is not None
    assert len(trace.windows) == 2
    assert len(trace.semantic_groups) == 1
    assert trace.semantic_groups[0].representative_window_id == (
        max(trace.windows, key=lambda window: window.end_x).window_id
    )


@pytest.mark.parametrize(
    ("height", "width", "gap"),
    [
        pytest.param(788, 1154, 22, id="nominal-gap-22"),
        pytest.param(640, 941, 22, id="resized-gap-22"),
        pytest.param(640, 941, 23, id="resized-gap-23"),
    ],
)
def test_exact_raster_support_deduplicates_fragmented_horizontal_line(
    height: int,
    width: int,
    gap: int,
) -> None:
    mask = _fragmented_marker_mask(height=height, width=width, gap=gap)

    analysis, _ = _analyze(mask, resolver=_FragmentedLineResolver(gap=gap))

    semantic = analysis.trace.semantic_search
    assert analysis.extraction.status is CurrentVisualPriceStatus.OK
    assert analysis.extraction.selected_y == height // 2
    assert semantic is not None
    assert semantic.evaluated_window_count == 2
    assert len(semantic.semantic_groups) == 1
    assert semantic.semantic_groups[0].line_hypothesis_ids == (
        "line_hypothesis_000",
        "line_hypothesis_001",
    )
    assert semantic.semantic_groups[0].representative_window_id == ("search_window_001")


def test_exact_multi_row_signature_merges_disjoint_provenance() -> None:
    candidates = (
        _semantic_candidate(
            "candidate_a",
            row_ids=(100, 101),
            line_ids=("line_a",),
        ),
        _semantic_candidate(
            "candidate_b",
            row_ids=(100, 101),
            line_ids=("line_b",),
            window_start=200,
            window_end=300,
            label_id="label_b",
        ),
    )

    groups = PocketOptionCurrentVisualPriceExtractor._semantic_candidate_groups(
        candidates
    )

    assert len(groups) == 1
    assert groups[0].line_hypothesis_ids == ("line_a", "line_b")


@pytest.mark.parametrize(
    ("left_rows", "right_rows"),
    [
        pytest.param((100, 101), (101, 102), id="partial-overlap"),
        pytest.param((100,), (101,), id="adjacent-rows"),
        pytest.param((), (), id="empty-signatures"),
    ],
)
def test_raster_support_fallback_requires_exact_non_empty_signature(
    left_rows: tuple[int, ...],
    right_rows: tuple[int, ...],
) -> None:
    candidates = (
        _semantic_candidate(
            "candidate_a",
            row_ids=left_rows,
            line_ids=("line_a",),
            y=100.5,
        ),
        _semantic_candidate(
            "candidate_b",
            row_ids=right_rows,
            line_ids=("line_b",),
            y=100.5,
        ),
    )

    groups = PocketOptionCurrentVisualPriceExtractor._semantic_candidate_groups(
        candidates
    )

    assert len(groups) == 2


def test_exact_raster_support_ignores_x_label_score_and_rightmost_position() -> None:
    candidates = (
        _semantic_candidate(
            "candidate_a",
            row_ids=(100,),
            line_ids=("line_a",),
            window_start=0,
            window_end=50,
            score=0.99,
            label_id="label_a",
        ),
        _semantic_candidate(
            "candidate_b",
            row_ids=(100,),
            line_ids=("line_b",),
            window_start=500,
            window_end=600,
            score=0.01,
            label_id="label_b",
        ),
    )

    groups = PocketOptionCurrentVisualPriceExtractor._semantic_candidate_groups(
        candidates
    )

    assert len(groups) == 1
    assert groups[0].representative.semantic_candidate_id == "candidate_b"


def test_mixed_provenance_and_raster_equivalence_is_transitive() -> None:
    candidates = (
        _semantic_candidate(
            "candidate_a",
            row_ids=(99,),
            line_ids=("shared_line",),
        ),
        _semantic_candidate(
            "candidate_b",
            row_ids=(100,),
            line_ids=("shared_line",),
        ),
        _semantic_candidate(
            "candidate_c",
            row_ids=(100,),
            line_ids=("fragmented_line",),
        ),
    )

    normal = PocketOptionCurrentVisualPriceExtractor._semantic_candidate_groups(
        candidates
    )
    reversed_order = PocketOptionCurrentVisualPriceExtractor._semantic_candidate_groups(
        tuple(reversed(candidates))
    )

    assert len(normal) == 1
    assert normal == reversed_order
    assert tuple(member.semantic_candidate_id for member in normal[0].members) == (
        "candidate_a",
        "candidate_b",
        "candidate_c",
    )


def test_same_selected_y_does_not_merge_different_raster_signatures() -> None:
    candidates = (
        _semantic_candidate(
            "candidate_a",
            row_ids=(100,),
            line_ids=("line_a",),
            y=100.5,
        ),
        _semantic_candidate(
            "candidate_b",
            row_ids=(101,),
            line_ids=("line_b",),
            y=100.5,
        ),
    )

    groups = PocketOptionCurrentVisualPriceExtractor._semantic_candidate_groups(
        candidates
    )

    assert len(groups) == 2


def test_f1021_equivalent_distinct_rows_remain_ambiguous() -> None:
    candidates = (
        _semantic_candidate(
            "candidate_a",
            row_ids=(121,),
            line_ids=("line_a",),
        ),
        _semantic_candidate(
            "candidate_b",
            row_ids=(398,),
            line_ids=("line_b",),
        ),
    )

    groups = PocketOptionCurrentVisualPriceExtractor._semantic_candidate_groups(
        candidates
    )

    assert len(groups) == 2


def test_f1067_equivalent_merges_only_duplicate_vertical_coordinate() -> None:
    candidates = tuple(
        _semantic_candidate(
            f"candidate_{index}",
            row_ids=(row_y,),
            line_ids=(f"line_{index}",),
        )
        for index, row_y in enumerate((121, 116, 171, 171))
    )

    groups = PocketOptionCurrentVisualPriceExtractor._semantic_candidate_groups(
        candidates
    )

    assert len(groups) == 3
    assert sorted(len(group.members) for group in groups) == [1, 1, 2]


def test_semantic_dedup_is_independent_of_window_iteration_order() -> None:
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[50, 79:95] = 255
    mask[47:50, 95:100] = 255
    mask[51:54, 93:98] = 255

    normal, _ = _analyze(mask)
    reversed_result, _ = _analyze(mask, resolver=_ReverseWindowResolver())

    assert normal.extraction == reversed_result.extraction
    assert normal.trace.semantic_search is not None
    assert reversed_result.trace.semantic_search is not None
    assert normal.trace.semantic_search.semantic_groups == (
        reversed_result.trace.semantic_search.semantic_groups
    )


def test_distinct_prices_in_same_overlapping_window_remain_distinct() -> None:
    mask = np.zeros((100, 100), dtype=np.uint8)
    _marker(
        mask,
        y=35,
        line_start=80,
        label_start=95,
        semantic_edge=100,
        radius=3,
    )
    _marker(
        mask,
        y=65,
        line_start=80,
        label_start=95,
        semantic_edge=100,
        radius=3,
    )

    analysis, _ = _analyze(mask)

    trace = analysis.trace.semantic_search
    assert analysis.extraction.status is (
        CurrentVisualPriceStatus.AMBIGUOUS_VISUAL_PRICE
    )
    assert analysis.extraction.selected_y is None
    assert analysis.extraction.confidence is None
    assert trace is not None
    assert len(trace.windows) == 1
    assert len(trace.semantic_groups) == 2
    assert trace.resolution_status is (
        CurrentVisualPriceSemanticResolutionStatus.AMBIGUOUS
    )
    assert trace.selected_group_id is None


def test_dynamic_empty_mask_remains_conservative_frame200_control() -> None:
    analysis, _ = _analyze(np.zeros((788, 1376), dtype=np.uint8))

    assert analysis.extraction.status is (
        CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE
    )
    assert analysis.extraction.price is None
    assert analysis.trace.semantic_search is not None
    assert analysis.trace.semantic_search.plan_reason is (
        CurrentVisualPriceSearchPlanReason.NO_MASK_PIXELS
    )


def test_window_limit_plan_is_not_partially_qualified() -> None:
    mask = np.zeros((100, 100), dtype=np.uint8)
    _marker(
        mask,
        y=50,
        line_start=80,
        label_start=95,
        semantic_edge=100,
    )

    analysis, _ = _analyze(mask, resolver=_UnavailableResolver())

    assert analysis.extraction.status is (
        CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE
    )
    assert analysis.trace.semantic_search is not None
    assert analysis.trace.semantic_search.evaluated_window_count == 0
    assert analysis.trace.semantic_search.plan_reason is (
        CurrentVisualPriceSearchPlanReason.WINDOW_LIMIT_EXCEEDED
    )


def test_qualifier_candidate_without_plan_provenance_fails_closed() -> None:
    mask = np.zeros((100, 100), dtype=np.uint8)
    _marker(
        mask,
        y=50,
        line_start=80,
        label_start=95,
        semantic_edge=100,
    )

    analysis, _ = _analyze(mask, resolver=_UnmappedCandidateResolver())

    assert analysis.extraction.status is (
        CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE
    )
    assert analysis.trace.candidates == ()
    assert analysis.trace.rejection_counts.candidate_groups == 0
    assert analysis.trace.semantic_search is not None
    assert analysis.trace.semantic_search.resolution_reason is (
        CurrentVisualPriceSemanticResolutionReason.NO_QUALIFYING_CANDIDATES
    )


def test_resolver_and_all_qualifiers_reuse_the_same_mask_object() -> None:
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[50, 79:95] = 255
    mask[47:50, 95:100] = 255
    mask[51:54, 93:98] = 255
    builder = _FixedMaskBuilder(mask)
    resolver = _RecordingResolver()
    extractor = _RecordingExtractor(
        mask_builder=builder,
        search_window_resolver=resolver,
    )

    analysis = extractor.extract_with_trace(np.zeros((100, 100, 3), dtype=np.uint8))

    assert analysis.extraction.status is CurrentVisualPriceStatus.OK
    assert resolver.mask is not None
    assert len(extractor.qualification_masks) == 2
    assert all(item is resolver.mask for item in extractor.qualification_masks)
    assert builder.calls == 1


@pytest.mark.parametrize("kind", ["line_only", "label_only", "side_panel"])
def test_incomplete_dynamic_evidence_never_creates_price(kind: str) -> None:
    mask = np.zeros((100, 120), dtype=np.uint8)
    if kind == "line_only":
        mask[50, 90:115] = 255
    elif kind == "label_only":
        mask[47:54, 110:120] = 255
    else:
        mask[20:80, 116:120] = 255

    analysis, _ = _analyze(mask)

    assert analysis.extraction.status is (
        CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE
    )
    assert analysis.extraction.price is None


@pytest.mark.parametrize(
    "mask",
    [
        np.zeros((1, 1), dtype=np.uint8),
        np.zeros((2, 3), dtype=np.uint8),
    ],
)
def test_tiny_roi_fails_closed_without_exception(mask: np.ndarray) -> None:
    analysis, _ = _analyze(mask)

    assert analysis.extraction.status is (
        CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE
    )


def test_dynamic_marker_near_top_has_no_safe_region_veto() -> None:
    mask = np.zeros((100, 100), dtype=np.uint8)
    _marker(
        mask,
        y=1,
        line_start=80,
        label_start=95,
        semantic_edge=100,
    )

    analysis, _ = _analyze(mask)

    assert analysis.extraction.status is CurrentVisualPriceStatus.OK
    assert analysis.extraction.selected_y == 1.0


@pytest.mark.parametrize(
    ("edge", "line_start", "label_start"),
    [
        (10, 8, 9),
        (100, 80, 95),
    ],
)
def test_semantic_edge_solver_handles_left_and_right_boundaries(
    edge: int,
    line_start: int,
    label_start: int,
) -> None:
    mask = np.zeros((100, 100), dtype=np.uint8)
    _marker(
        mask,
        y=50,
        line_start=line_start,
        label_start=label_start,
        semantic_edge=edge,
        radius=3,
    )

    analysis, _ = _analyze(mask)

    assert analysis.extraction.status is CurrentVisualPriceStatus.OK
    assert analysis.trace.band_end == edge
    assert analysis.trace.band_start == edge - ceil(edge * 0.20)
