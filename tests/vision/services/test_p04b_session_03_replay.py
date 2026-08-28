from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import cv2
import pytest

from pocket_option_analyzer.application.signals import (
    VisualStrategySignalAnalysisPipeline,
)
from pocket_option_analyzer.application.strategy import (
    CurrentVisualPriceComparator,
    CurrentVisualPriceComparisonContext,
    CurrentVisualPriceComparisonStatus,
    VisualPriceReference,
    VisualPriceReferenceResult,
    VisualPriceReferenceStatus,
)
from pocket_option_analyzer.application.strategy.visual_reference_validation import (
    references_are_comparable,
)
from pocket_option_analyzer.infrastructure.bootstrap import SignalPipelineFactory
from pocket_option_analyzer.vision.models import (
    CandleColorProfile,
    CandleOverlayEvidenceStatus,
    CandleSeriesExtensionDecision,
    CandleSeriesMembershipExclusionReason,
    CandleSeriesMembershipStatus,
    ChartRegion,
    CurrentVisualPriceSearchPlanReason,
    CurrentVisualPriceStatus,
    MarketAnalysis,
)


@dataclass(frozen=True, slots=True)
class _FrameOracle:
    frame_id: int
    frame_key: str
    phase: str
    snapshot_id: str
    latest_candidate_id: str
    latest_x: int


@dataclass(frozen=True, slots=True)
class _ReplayResult:
    oracle: _FrameOracle
    analysis: MarketAnalysis
    reference_result: VisualPriceReferenceResult
    persisted_current_visual_price: dict[str, object]


# Oracle de regresión derivado de la revisión visual de P0.4b session 03.
# Los IDs y coordenadas se usan solo en tests, nunca en código productivo.
_ORACLES = (
    _FrameOracle(
        1,
        "frame_00000001_20260818T183744266622Z",
        "entry",
        "2026-08-18T18:37:30+00:00",
        "candidate_019",
        695,
    ),
    _FrameOracle(
        11,
        "frame_00000011_20260818T183754981798Z",
        "exit",
        "2026-08-18T18:37:30+00:00",
        "candidate_020",
        695,
    ),
    _FrameOracle(
        13,
        "frame_00000013_20260818T183813500479Z",
        "entry",
        "2026-08-18T18:38:00+00:00",
        "candidate_009",
        695,
    ),
    _FrameOracle(
        23,
        "frame_00000023_20260818T183824195634Z",
        "exit",
        "2026-08-18T18:38:00+00:00",
        "candidate_012",
        695,
    ),
    _FrameOracle(
        28,
        "frame_00000028_20260818T183839000893Z",
        "entry",
        "2026-08-18T18:38:30+00:00",
        "candidate_021",
        695,
    ),
    _FrameOracle(
        38,
        "frame_00000038_20260818T183849677555Z",
        "exit",
        "2026-08-18T18:38:30+00:00",
        "candidate_023",
        695,
    ),
    _FrameOracle(
        44,
        "frame_00000044_20260818T184114925440Z",
        "entry",
        "2026-08-18T18:41:00+00:00",
        "candidate_023",
        695,
    ),
    _FrameOracle(
        47,
        "frame_00000047_20260818T184125568207Z",
        "exit",
        "2026-08-18T18:41:00+00:00",
        "candidate_023",
        695,
    ),
    _FrameOracle(
        53,
        "frame_00000053_20260818T184131985255Z",
        "entry",
        "2026-08-18T18:41:30+00:00",
        "candidate_014",
        695,
    ),
    _FrameOracle(
        63,
        "frame_00000063_20260818T184142634884Z",
        "exit",
        "2026-08-18T18:41:30+00:00",
        "candidate_033",
        695,
    ),
    _FrameOracle(
        76,
        "frame_00000076_20260818T184202116516Z",
        "entry",
        "2026-08-18T18:42:00+00:00",
        "candidate_034",
        695,
    ),
    _FrameOracle(
        86,
        "frame_00000086_20260818T184212749289Z",
        "exit",
        "2026-08-18T18:42:00+00:00",
        "candidate_039",
        695,
    ),
    _FrameOracle(
        88,
        "frame_00000088_20260818T184233553839Z",
        "entry",
        "2026-08-18T18:42:30+00:00",
        "candidate_017",
        695,
    ),
    _FrameOracle(
        98,
        "frame_00000098_20260818T184244334249Z",
        "exit",
        "2026-08-18T18:42:30+00:00",
        "candidate_036",
        695,
    ),
    _FrameOracle(
        115,
        "frame_00000115_20260818T184302446004Z",
        "entry",
        "2026-08-18T18:43:00+00:00",
        "candidate_012",
        695,
    ),
    _FrameOracle(
        125,
        "frame_00000125_20260818T184313094305Z",
        "exit",
        "2026-08-18T18:43:00+00:00",
        "candidate_021",
        695,
    ),
    _FrameOracle(
        143,
        "frame_00000143_20260818T184332143408Z",
        "entry",
        "2026-08-18T18:43:30+00:00",
        "candidate_008",
        694,
    ),
    _FrameOracle(
        153,
        "frame_00000153_20260818T184342810108Z",
        "exit",
        "2026-08-18T18:43:30+00:00",
        "candidate_023",
        695,
    ),
    _FrameOracle(
        172,
        "frame_00000172_20260818T184402976152Z",
        "entry",
        "2026-08-18T18:44:00+00:00",
        "candidate_008",
        695,
    ),
    _FrameOracle(
        182,
        "frame_00000182_20260818T184413608346Z",
        "exit",
        "2026-08-18T18:44:00+00:00",
        "candidate_011",
        695,
    ),
    _FrameOracle(
        200,
        "frame_00000200_20260818T184432707148Z",
        "entry",
        "2026-08-18T18:44:30+00:00",
        "candidate_004",
        669,
    ),
)


def _session_directory() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "logs"
        / "calibration"
        / "p04b_session_03"
        / "evidence"
    )


@lru_cache(maxsize=1)
def _replay_session() -> tuple[_ReplayResult, ...]:
    session_directory = _session_directory()
    try:
        available = session_directory.is_dir()
    except OSError:
        available = False
    if not available:
        pytest.skip("P0.4b session03 evidence is not available locally.")

    pipeline = SignalPipelineFactory._create_market_analysis_pipeline(
        color_profile=CandleColorProfile.white_red(),
    )
    results = []
    for oracle in _ORACLES:
        image_path = session_directory / "frames" / oracle.frame_key / "chart.png"
        image = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
        if image is None:
            pytest.skip(f"Unable to read local replay image: {image_path}")
        region = ChartRegion(
            x=0,
            y=0,
            width=int(image.shape[1]),
            height=int(image.shape[0]),
        )
        analysis = pipeline.analyze(
            image,
            price_observation_image=image,
            chart_region=region,
            price_observation_region=region,
        )
        frame_metadata = json.loads(
            (session_directory / "frames" / oracle.frame_key / "frame.json").read_text(
                encoding="utf-8"
            )
        )
        results.append(
            _ReplayResult(
                oracle=oracle,
                analysis=analysis,
                reference_result=(
                    VisualStrategySignalAnalysisPipeline._price_reference_result(
                        analysis
                    )
                ),
                persisted_current_visual_price=frame_metadata["analysis"][
                    "current_visual_price"
                ],
            )
        )
    return tuple(results)


def _result(frame_id: int) -> _ReplayResult:
    return next(
        result for result in _replay_session() if result.oracle.frame_id == frame_id
    )


def _snapshot_pair(snapshot_id: str) -> tuple[_ReplayResult, _ReplayResult]:
    matching = tuple(
        result
        for result in _replay_session()
        if result.oracle.snapshot_id == snapshot_id
    )
    entry = next(result for result in matching if result.oracle.phase == "entry")
    exit_result = next(result for result in matching if result.oracle.phase == "exit")
    return entry, exit_result


def test_session_03_replay_selects_all_twenty_one_true_latest_candles() -> None:
    results = _replay_session()

    assert len(results) == 21
    for result in results:
        trace = result.analysis.candle_detection_trace
        assert trace is not None and trace.series_membership is not None
        membership = trace.series_membership
        assert membership.status is CandleSeriesMembershipStatus.AVAILABLE
        assert membership.latest_candidate_id == result.oracle.latest_candidate_id
        assert result.analysis.series.latest is not None
        assert result.analysis.series.latest.candidate.x == result.oracle.latest_x


def test_session_03_expiry_caps_remain_visible_but_outside_membership() -> None:
    for result in _replay_session():
        trace = result.analysis.candle_detection_trace
        assert trace is not None and trace.series_membership is not None
        final_by_id = {item.candidate_id: item for item in trace.final_candles}
        cap_ids = tuple(
            candidate_id
            for candidate_id, item in final_by_id.items()
            if 710 <= item.x <= 760 and item.y <= 40
        )
        assert cap_ids
        for candidate_id in cap_ids:
            assert candidate_id not in trace.series_membership.member_candidate_ids


def test_session_03_observable_visual_references_remain_available() -> None:
    results = _replay_session()

    assert all(
        result.reference_result.status is VisualPriceReferenceStatus.OK
        for result in results
        if result.oracle.frame_id != 200
    )
    off_roi = _result(200).reference_result
    assert off_roi.status is (
        VisualPriceReferenceStatus.CURRENT_CLOSE_NOT_OBSERVABLE
    )
    assert off_roi.reference is None
    assert off_roi.close_roi_y == 787


def test_session_03_frame_63_repairs_only_expiry_overlay_membership() -> None:
    result = _result(63)
    analysis = result.analysis
    trace = analysis.candle_detection_trace
    assert trace is not None
    assert trace.series_membership is not None
    assert trace.overlay_evidence is not None
    membership = trace.series_membership
    final_ids = tuple(item.candidate_id for item in trace.final_candles)
    exclusions = {item.candidate_id: item for item in membership.excluded_candidates}

    assert "candidate_083" in final_ids
    assert "candidate_033" in membership.member_candidate_ids
    assert membership.latest_candidate_id == "candidate_033"
    assert exclusions["candidate_083"].reason is (
        CandleSeriesMembershipExclusionReason.EXPIRY_OVERLAY
    )
    overlay = trace.overlay_evidence.by_candidate_id()["candidate_083"]
    assert overlay.status is CandleOverlayEvidenceStatus.EXPIRY_OVERLAY
    extension = next(
        item
        for item in membership.extension_decisions
        if item.candidate_id == "candidate_083"
    )
    assert "candidate_083" not in extension.core_candidate_ids
    assert extension.frozen_vertical_median_gap_px == pytest.approx(9.0)
    assert extension.frozen_vertical_mad_px == pytest.approx(9.0)
    assert extension.frozen_body_height_scale_px == pytest.approx(84.0)
    assert extension.frozen_robust_allowance_px == pytest.approx(63.0)
    assert extension.frozen_body_allowance_px == pytest.approx(168.0)
    assert extension.frozen_vertical_continuity_limit_px == pytest.approx(168.0)
    assert extension.candidate_vertical_gap_px == pytest.approx(153.0)
    assert extension.decision is (CandleSeriesExtensionDecision.EXCLUDED_EXPIRY_OVERLAY)

    assert result.reference_result.status is VisualPriceReferenceStatus.OK
    assert result.reference_result.close_roi_y != 11
    reference_analysis = VisualStrategySignalAnalysisPipeline._price_reference_analysis(
        analysis
    )
    enriched = VisualStrategySignalAnalysisPipeline._with_reference_roles(
        market_analysis=analysis,
        reference_analysis=reference_analysis,
    )
    assert enriched.candle_detection_trace is not None
    roles = {
        item.candidate_id: item
        for item in enriched.candle_detection_trace.final_candles
    }
    assert roles["candidate_083"].is_anchor is False
    assert roles["candidate_033"].is_latest is True
    assert roles["candidate_033"].is_anchor is False


def test_session_03_frame_172_price_text_remains_horizontal_outlier() -> None:
    trace = _result(172).analysis.candle_detection_trace
    assert trace is not None and trace.series_membership is not None
    exclusion = next(
        item
        for item in trace.series_membership.excluded_candidates
        if item.candidate_id == "candidate_002"
    )

    assert exclusion.reason is (
        CandleSeriesMembershipExclusionReason.HORIZONTAL_OUTLIER
    )


def test_session_03_autoscale_pair_remains_comparable_under_point_zero_two() -> None:
    entry, exit_result = _snapshot_pair("2026-08-18T18:42:00+00:00")
    entry_reference: VisualPriceReference | None = entry.reference_result.reference
    exit_reference: VisualPriceReference | None = exit_result.reference_result.reference

    assert entry_reference is not None
    assert exit_reference is not None
    assert references_are_comparable(entry_reference, exit_reference)
    maximum_difference = max(
        abs(entry_value - exit_value)
        for entry_anchor, exit_anchor in zip(
            entry_reference.anchor_shape,
            exit_reference.anchor_shape,
            strict=True,
        )
        for entry_value, exit_value in zip(
            entry_anchor[1:],
            exit_anchor[1:],
            strict=True,
        )
    )
    assert maximum_difference < 0.02


def test_session_03_detects_all_twenty_visible_current_price_markers() -> None:
    marker_results = tuple(
        result for result in _replay_session() if result.oracle.frame_id != 200
    )

    assert len(marker_results) == 20
    assert all(
        result.analysis.current_visual_price is not None
        and result.analysis.current_visual_price.status is CurrentVisualPriceStatus.OK
        for result in marker_results
    )


def test_session_03_frame_53_current_price_is_recovered_at_visual_row() -> None:
    result = _result(53)
    extraction = result.analysis.current_visual_price

    assert result.persisted_current_visual_price["status"] == (
        "no_visual_price_candidate"
    )
    assert extraction is not None
    assert extraction.status is CurrentVisualPriceStatus.OK
    assert extraction.price is not None
    assert extraction.price.roi_y == pytest.approx(336.0, abs=1.0)
    trace = result.analysis.current_visual_price_detection_trace
    assert trace is not None
    row = next(row for row in trace.row_evaluations if row.qualified)
    assert row.row_y == 336
    assert row.line_run_span_ratio >= 0.70
    assert row.line_run_continuity >= 0.90
    assert row.line_evidence is True
    assert row.label_support is True


def test_session_03_frame_200_remains_without_current_price_candidate() -> None:
    result = _result(200)
    extraction = result.analysis.current_visual_price

    assert extraction is not None
    assert extraction.status is (CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE)
    trace = result.analysis.current_visual_price_detection_trace
    assert trace is not None
    assert trace.row_evaluations == ()
    assert trace.semantic_search is not None
    assert trace.semantic_search.plan_reason is (
        CurrentVisualPriceSearchPlanReason.NO_HORIZONTAL_LINE_HYPOTHESES
    )
    assert trace.rejection_counts.line_evidence_rows == 0
    assert (
        trace.rejection_counts.rows_without_mask_pixels
        + trace.rejection_counts.rows_with_mask_pixels
        == trace.image_height
    )


def test_session_03_preserves_roi_y_for_previously_available_frames() -> None:
    compared = 0
    for result in _replay_session():
        persisted = result.persisted_current_visual_price
        if persisted["status"] != "ok":
            continue
        current = result.analysis.current_visual_price
        assert current is not None and current.price is not None
        persisted_price = persisted["price"]
        assert isinstance(persisted_price, dict)
        assert abs(current.price.roi_y - persisted_price["roi_y"]) <= 0.5
        compared += 1

    assert compared == 19


def test_session_03_184130_visual_price_comparison_becomes_available() -> None:
    entry, exit_result = _snapshot_pair("2026-08-18T18:41:30+00:00")
    entry_context = CurrentVisualPriceComparisonContext(
        current_visual_price=entry.analysis.current_visual_price,
        chart_region=entry.analysis.chart_region,
        price_observation_region=entry.analysis.price_observation_region,
        reference_result=entry.reference_result,
    )
    exit_context = CurrentVisualPriceComparisonContext(
        current_visual_price=exit_result.analysis.current_visual_price,
        chart_region=exit_result.analysis.chart_region,
        price_observation_region=exit_result.analysis.price_observation_region,
        reference_result=exit_result.reference_result,
    )
    comparison = CurrentVisualPriceComparator().compare(
        entry_context,
        exit_context,
    )

    assert comparison.status is CurrentVisualPriceComparisonStatus.AVAILABLE
    assert comparison.delta is not None
    assert comparison.entry_anchor_span_px == pytest.approx(648.0)
    assert comparison.exit_anchor_span_px == pytest.approx(648.0)
