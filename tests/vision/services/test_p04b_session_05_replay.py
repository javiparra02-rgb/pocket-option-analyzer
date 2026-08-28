from __future__ import annotations

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
    VisualPriceReferenceResult,
    VisualPriceReferenceStatus,
)
from pocket_option_analyzer.infrastructure.bootstrap import SignalPipelineFactory
from pocket_option_analyzer.vision.models import (
    CandleColorProfile,
    ChartRegion,
    CurrentVisualPriceSearchPlanReason,
    CurrentVisualPriceStatus,
    MarketAnalysis,
)


@dataclass(frozen=True, slots=True)
class _FrameOracle:
    frame_id: int
    frame_key: str
    expected_status: CurrentVisualPriceStatus
    selected_y: float | None
    decision_diagnostic: str


@dataclass(frozen=True, slots=True)
class _ReplayResult:
    oracle: _FrameOracle
    analysis: MarketAnalysis
    reference_result: VisualPriceReferenceResult


_ORACLES = (
    _FrameOracle(
        1,
        "frame_00000001_20260823T202231602142Z",
        CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE,
        None,
        "no_horizontal_line_hypotheses",
    ),
    _FrameOracle(
        11,
        "frame_00000011_20260823T202242463685Z",
        CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE,
        None,
        "semantic_windows_without_qualifying_candidate",
    ),
    _FrameOracle(
        30,
        "frame_00000030_20260823T202302830489Z",
        CurrentVisualPriceStatus.OK,
        774.0,
        "candidate_available",
    ),
    _FrameOracle(
        40,
        "frame_00000040_20260823T202313695589Z",
        CurrentVisualPriceStatus.OK,
        735.0,
        "candidate_available",
    ),
    _FrameOracle(
        57,
        "frame_00000057_20260823T202332010478Z",
        CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE,
        None,
        "no_horizontal_line_hypotheses",
    ),
    _FrameOracle(
        67,
        "frame_00000067_20260823T202342844955Z",
        CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE,
        None,
        "no_compatible_line_label_pairs",
    ),
)


def _session_directory() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "logs"
        / "calibration"
        / "p04b_session_05"
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
        pytest.skip("P0.4b session05 evidence is not available locally.")

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
        results.append(
            _ReplayResult(
                oracle=oracle,
                analysis=analysis,
                reference_result=(
                    VisualStrategySignalAnalysisPipeline._price_reference_result(
                        analysis
                    )
                ),
            )
        )
    return tuple(results)


def _result(frame_id: int) -> _ReplayResult:
    return next(
        result for result in _replay_session() if result.oracle.frame_id == frame_id
    )


def _comparison_context(result: _ReplayResult) -> CurrentVisualPriceComparisonContext:
    return CurrentVisualPriceComparisonContext(
        current_visual_price=result.analysis.current_visual_price,
        chart_region=result.analysis.chart_region,
        price_observation_region=result.analysis.price_observation_region,
        reference_result=result.reference_result,
    )


def test_session_05_current_visual_price_matrix_is_observability_first() -> None:
    results = _replay_session()

    assert len(results) == 6
    for result in results:
        extraction = result.analysis.current_visual_price
        trace = result.analysis.current_visual_price_detection_trace
        assert extraction is not None and trace is not None
        assert extraction.status is result.oracle.expected_status
        assert extraction.selected_y == result.oracle.selected_y
        assert trace.decision_diagnostic == result.oracle.decision_diagnostic


@pytest.mark.parametrize(
    ("frame_id", "expected_status"),
    (
        (1, VisualPriceReferenceStatus.CURRENT_CLOSE_NOT_OBSERVABLE),
        (11, VisualPriceReferenceStatus.CURRENT_CLOSE_NOT_OBSERVABLE),
        (30, VisualPriceReferenceStatus.OK),
        (40, VisualPriceReferenceStatus.OK),
        (57, VisualPriceReferenceStatus.CURRENT_CLOSE_NOT_OBSERVABLE),
        (67, VisualPriceReferenceStatus.CURRENT_CLOSE_NOT_OBSERVABLE),
    ),
)
def test_session_05_reference_observability_matrix(
    frame_id: int,
    expected_status: VisualPriceReferenceStatus,
) -> None:
    result = _result(frame_id).reference_result

    assert result.status is expected_status
    assert result.is_available is (expected_status is VisualPriceReferenceStatus.OK)
    if expected_status is VisualPriceReferenceStatus.CURRENT_CLOSE_NOT_OBSERVABLE:
        assert result.reference is None
        assert result.close_roi_y == 787


def test_session_05_observability_stays_associated_with_productive_latest() -> None:
    for result in _replay_session():
        latest = result.analysis.series.latest
        trace = result.analysis.candle_detection_trace
        assert latest is not None
        assert trace is not None
        latest_trace = next(
            candle for candle in trace.final_candles if candle.is_latest
        )
        assert latest.candidate.geometry is not None
        assert latest.candidate.observability is not None
        assert latest_trace.observability is latest.candidate.observability
        assert latest_trace.observability.roi_height == 788
        assert latest_trace.observability.body_top_y == (
            latest.candidate.geometry.body_top_y
        )
        assert latest_trace.observability.body_bottom_y == (
            latest.candidate.geometry.body_bottom_y
        )


def test_session_05_frame_30_accepts_trusted_marker_outside_legacy_margin() -> None:
    result = _result(30)
    extraction = result.analysis.current_visual_price
    trace = result.analysis.current_visual_price_detection_trace

    assert extraction is not None and extraction.price is not None
    assert extraction.status is CurrentVisualPriceStatus.OK
    assert extraction.price.roi_y == pytest.approx(774.0, abs=0.5)
    assert trace is not None
    assert (trace.safe_top, trace.safe_bottom) == (40, 40)
    assert extraction.price.roi_y > 787 - trace.safe_bottom
    row = next(row for row in trace.row_evaluations if row.qualified)
    assert row.line_run_span_ratio >= 0.70
    assert row.line_run_continuity >= 0.90
    assert row.label_support is True
    assert row.label_support_trace is not None
    assert row.label_support_trace.supported is True
    assert row.label_support_trace.support_row_count > 0
    assert row.label_support_trace.support_density >= 0.05
    assert result.reference_result.close_roi_y == 773
    assert abs(extraction.price.roi_y - result.reference_result.close_roi_y) == 1


def test_session_05_frame_40_uses_semantic_window_without_changing_price() -> None:
    result = _result(40)
    extraction = result.analysis.current_visual_price
    trace = result.analysis.current_visual_price_detection_trace

    assert extraction is not None and extraction.price is not None
    assert extraction.status is CurrentVisualPriceStatus.OK
    assert extraction.price.roi_y == pytest.approx(735.0, abs=0.5)
    assert trace is not None
    row = next(row for row in trace.row_evaluations if row.qualified)
    assert trace.effective_chart_right_source == "semantic_resolver"
    assert row.line_evidence is True
    assert row.label_support is True
    assert result.reference_result.close_roi_y == 736
    assert abs(extraction.price.roi_y - result.reference_result.close_roi_y) == 1


def test_session_05_frame_57_rejects_partial_label_without_semantic_line() -> None:
    result = _result(57)
    extraction = result.analysis.current_visual_price
    trace = result.analysis.current_visual_price_detection_trace

    assert extraction is not None
    assert extraction.status is CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE
    assert trace is not None
    assert trace.row_evaluations == ()
    assert trace.semantic_search is not None
    assert trace.semantic_search.plan_reason is (
        CurrentVisualPriceSearchPlanReason.NO_HORIZONTAL_LINE_HYPOTHESES
    )
    assert trace.decision_diagnostic == "no_horizontal_line_hypotheses"


def test_session_05_snapshot_two_current_price_comparison_is_available() -> None:
    entry = _result(30)
    exit_result = _result(40)

    assert entry.reference_result.status is VisualPriceReferenceStatus.OK
    assert exit_result.reference_result.status is VisualPriceReferenceStatus.OK
    entry_reference = entry.reference_result.reference
    exit_reference = exit_result.reference_result.reference
    assert entry_reference is not None and exit_reference is not None
    assert len(entry_reference.anchor_shape) == 27
    assert entry_reference.anchor_shape == exit_reference.anchor_shape

    comparison = CurrentVisualPriceComparator().compare(
        _comparison_context(entry),
        _comparison_context(exit_result),
    )

    assert comparison.status is CurrentVisualPriceComparisonStatus.AVAILABLE
    assert comparison.entry_anchored_value == pytest.approx(0.0196078431372549)
    assert comparison.exit_anchored_value == pytest.approx(0.0784313725490196)
    assert comparison.delta == pytest.approx(0.0588235294117647)
