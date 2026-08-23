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
    CurrentVisualPriceComparisonDiagnostic,
    CurrentVisualPriceComparisonStatus,
    PriceMovement,
    VisualPriceReferenceResult,
    VisualPriceReferenceStatus,
)
from pocket_option_analyzer.application.strategy.visual_reference_validation import (
    compare_visual_references,
    references_are_comparable,
)
from pocket_option_analyzer.infrastructure.bootstrap import SignalPipelineFactory
from pocket_option_analyzer.vision.models import (
    CandleColorProfile,
    CandleSeriesMembershipStatus,
    ChartRegion,
    MarketAnalysis,
)


@dataclass(frozen=True, slots=True)
class _FrameOracle:
    frame_id: int
    frame_key: str
    latest_candidate_id: str


@dataclass(frozen=True, slots=True)
class _ReplayResult:
    oracle: _FrameOracle
    analysis: MarketAnalysis
    reference_result: VisualPriceReferenceResult


@dataclass(frozen=True, slots=True)
class _SnapshotOracle:
    snapshot_id: str
    entry_frame_id: int
    exit_frame_id: int
    entry_reference_value: float
    exit_reference_value: float
    comparable: bool
    movement: PriceMovement


_FRAMES = (
    _FrameOracle(
        1,
        "frame_00000001_20260823T014159232719Z",
        "candidate_036",
    ),
    _FrameOracle(
        2,
        "frame_00000002_20260823T014212274040Z",
        "candidate_039",
    ),
    _FrameOracle(
        12,
        "frame_00000012_20260823T014223134166Z",
        "candidate_040",
    ),
    _FrameOracle(
        21,
        "frame_00000021_20260823T014232866917Z",
        "candidate_037",
    ),
    _FrameOracle(
        26,
        "frame_00000026_20260823T014248155761Z",
        "candidate_037",
    ),
)

_SNAPSHOTS = (
    _SnapshotOracle(
        snapshot_id="2026-08-23T01:41:30+00:00",
        entry_frame_id=1,
        exit_frame_id=2,
        entry_reference_value=1.0363924050632911,
        exit_reference_value=1.0540983606557377,
        comparable=False,
        movement=PriceMovement.UNRESOLVED,
    ),
    _SnapshotOracle(
        snapshot_id="2026-08-23T01:42:00+00:00",
        entry_frame_id=2,
        exit_frame_id=12,
        entry_reference_value=1.0540983606557377,
        exit_reference_value=0.9180327868852459,
        comparable=True,
        movement=PriceMovement.DOWN,
    ),
    _SnapshotOracle(
        snapshot_id="2026-08-23T01:42:30+00:00",
        entry_frame_id=21,
        exit_frame_id=26,
        entry_reference_value=1.021978021978022,
        exit_reference_value=1.0679933665008292,
        comparable=True,
        movement=PriceMovement.UP,
    ),
)


def _session_directory() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "logs"
        / "calibration"
        / "p04b_session_04"
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
        pytest.skip("P0.4b session04 evidence is not available locally.")

    pipeline = SignalPipelineFactory._create_market_analysis_pipeline(
        color_profile=CandleColorProfile.white_red(),
    )
    results = []
    for oracle in _FRAMES:
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


def _snapshot_pair(
    snapshot_id: str,
) -> tuple[_SnapshotOracle, _ReplayResult, _ReplayResult]:
    oracle = next(item for item in _SNAPSHOTS if item.snapshot_id == snapshot_id)
    return oracle, _result(oracle.entry_frame_id), _result(oracle.exit_frame_id)


def _comparison_context(
    result: _ReplayResult,
) -> CurrentVisualPriceComparisonContext:
    return CurrentVisualPriceComparisonContext(
        current_visual_price=result.analysis.current_visual_price,
        chart_region=result.analysis.chart_region,
        price_observation_region=result.analysis.price_observation_region,
        reference_result=result.reference_result,
    )


def _assert_reference_pair(
    oracle: _SnapshotOracle,
    entry: _ReplayResult,
    exit_result: _ReplayResult,
) -> None:
    assert entry.reference_result.status is VisualPriceReferenceStatus.OK
    assert exit_result.reference_result.status is VisualPriceReferenceStatus.OK
    entry_reference = entry.reference_result.reference
    exit_reference = exit_result.reference_result.reference
    assert entry_reference is not None
    assert exit_reference is not None
    assert entry_reference.value == pytest.approx(oracle.entry_reference_value)
    assert exit_reference.value == pytest.approx(oracle.exit_reference_value)
    assert len(entry_reference.anchor_shape) == 27
    assert len(exit_reference.anchor_shape) == 27
    assert references_are_comparable(entry_reference, exit_reference) is (
        oracle.comparable
    )
    assert compare_visual_references(entry_reference, exit_reference) is (
        oracle.movement
    )


def test_session_04_replay_preserves_trusted_candle_membership() -> None:
    results = _replay_session()

    assert len(results) == 5
    for result in results:
        trace = result.analysis.candle_detection_trace
        assert trace is not None and trace.series_membership is not None
        membership = trace.series_membership
        assert membership.status is CandleSeriesMembershipStatus.AVAILABLE
        assert membership.latest_candidate_id == result.oracle.latest_candidate_id
        assert len(membership.member_candidate_ids) == 28


def test_session_04_snapshot_one_keeps_incompatible_anchor_shapes() -> None:
    oracle, entry, exit_result = _snapshot_pair("2026-08-23T01:41:30+00:00")

    _assert_reference_pair(oracle, entry, exit_result)
    comparison = CurrentVisualPriceComparator().compare(
        _comparison_context(entry),
        _comparison_context(exit_result),
    )

    assert comparison.status is CurrentVisualPriceComparisonStatus.UNAVAILABLE
    assert comparison.diagnostic is (
        CurrentVisualPriceComparisonDiagnostic.REFERENCES_NOT_COMPARABLE
    )


def test_session_04_snapshot_two_resolves_breakout_pair_down() -> None:
    oracle, entry, exit_result = _snapshot_pair("2026-08-23T01:42:00+00:00")

    _assert_reference_pair(oracle, entry, exit_result)
    entry_reference = entry.reference_result.reference
    exit_reference = exit_result.reference_result.reference
    assert entry_reference is not None and exit_reference is not None
    assert entry_reference.anchor_shape == exit_reference.anchor_shape
    comparison = CurrentVisualPriceComparator().compare(
        _comparison_context(entry),
        _comparison_context(exit_result),
    )

    assert comparison.status is CurrentVisualPriceComparisonStatus.AVAILABLE
    assert comparison.entry_anchored_value == pytest.approx(1.0557377049180328)
    assert comparison.exit_anchored_value == pytest.approx(0.9163934426229509)
    assert comparison.delta == pytest.approx(-0.1393442622950819)


def test_session_04_snapshot_three_resolves_breakout_pair_up() -> None:
    oracle, entry, exit_result = _snapshot_pair("2026-08-23T01:42:30+00:00")

    _assert_reference_pair(oracle, entry, exit_result)
    entry_reference = entry.reference_result.reference
    exit_reference = exit_result.reference_result.reference
    assert entry_reference is not None and exit_reference is not None
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
    assert maximum_difference == pytest.approx(0.00709430346956999)
    assert maximum_difference < 0.02
    comparison = CurrentVisualPriceComparator().compare(
        _comparison_context(entry),
        _comparison_context(exit_result),
    )

    assert comparison.status is CurrentVisualPriceComparisonStatus.AVAILABLE
    assert comparison.entry_anchored_value == pytest.approx(1.022765000758287)
    assert comparison.exit_anchored_value == pytest.approx(1.0696517412935322)
    assert comparison.delta == pytest.approx(0.04688674053524533)
