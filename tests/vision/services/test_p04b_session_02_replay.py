from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import pytest

from pocket_option_analyzer.application.signals import (
    VisualStrategySignalAnalysisPipeline,
)
from pocket_option_analyzer.application.strategy import (
    VisualPriceReference,
    VisualPriceReferenceStatus,
)
from pocket_option_analyzer.application.strategy.visual_reference_validation import (
    references_are_comparable,
)
from pocket_option_analyzer.infrastructure.bootstrap import SignalPipelineFactory
from pocket_option_analyzer.vision.models import (
    CandleColorProfile,
    CandleSeriesMembershipStatus,
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
    flag_candidate_id: str
    price_text_candidate_id: str | None


@dataclass(frozen=True, slots=True)
class _ReplayResult:
    oracle: _FrameOracle
    analysis: MarketAnalysis
    reference_status: VisualPriceReferenceStatus
    reference: VisualPriceReference | None


# Oracle exclusivo de regresión, derivado de frame.json de P0.4b session 02.
# Estos IDs/coordenadas nunca son consumidos por código productivo.
_ORACLES = (
    _FrameOracle(
        1,
        "frame_00000001_20260817T231512716023Z",
        "entry",
        "2026-08-17T23:15:00+00:00",
        "candidate_033",
        694,
        "candidate_080",
        None,
    ),
    _FrameOracle(
        11,
        "frame_00000011_20260817T231523395322Z",
        "exit",
        "2026-08-17T23:15:00+00:00",
        "candidate_034",
        694,
        "candidate_081",
        "candidate_030",
    ),
    _FrameOracle(
        20,
        "frame_00000020_20260817T231532978156Z",
        "entry",
        "2026-08-17T23:15:30+00:00",
        "candidate_025",
        693,
        "candidate_081",
        "candidate_027",
    ),
    _FrameOracle(
        30,
        "frame_00000030_20260817T231543627812Z",
        "exit",
        "2026-08-17T23:15:30+00:00",
        "candidate_029",
        693,
        "candidate_080",
        "candidate_022",
    ),
    _FrameOracle(
        48,
        "frame_00000048_20260817T231602693798Z",
        "entry",
        "2026-08-17T23:16:00+00:00",
        "candidate_024",
        693,
        "candidate_082",
        None,
    ),
    _FrameOracle(
        58,
        "frame_00000058_20260817T231613293057Z",
        "exit",
        "2026-08-17T23:16:00+00:00",
        "candidate_022",
        693,
        "candidate_080",
        "candidate_016",
    ),
    _FrameOracle(
        76,
        "frame_00000076_20260817T231632407982Z",
        "entry",
        "2026-08-17T23:16:30+00:00",
        "candidate_017",
        694,
        "candidate_082",
        None,
    ),
    _FrameOracle(
        86,
        "frame_00000086_20260817T231643041855Z",
        "exit",
        "2026-08-17T23:16:30+00:00",
        "candidate_023",
        693,
        "candidate_082",
        None,
    ),
    _FrameOracle(
        104,
        "frame_00000104_20260817T231702106984Z",
        "entry",
        "2026-08-17T23:17:00+00:00",
        "candidate_008",
        694,
        "candidate_080",
        "candidate_009",
    ),
    _FrameOracle(
        114,
        "frame_00000114_20260817T231712739760Z",
        "exit",
        "2026-08-17T23:17:00+00:00",
        "candidate_009",
        694,
        "candidate_082",
        None,
    ),
)


def _session_directory() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "logs"
        / "calibration"
        / "p04b_session_02"
        / "evidence"
    )


def _replay_session() -> tuple[_ReplayResult, ...]:
    session_directory = _session_directory()
    try:
        available = session_directory.is_dir()
    except OSError:
        available = False
    if not available:
        pytest.skip("P0.4b session02 evidence is not available locally.")

    pipeline = SignalPipelineFactory._create_market_analysis_pipeline(
        color_profile=CandleColorProfile.white_red(),
    )
    results = []
    for oracle in _ORACLES:
        image_path = session_directory / "frames" / oracle.frame_key / "chart.png"
        image = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
        if image is None:
            pytest.skip(f"Unable to read local replay image: {image_path}")
        analysis = pipeline.analyze(image)
        reference_result = (
            VisualStrategySignalAnalysisPipeline._price_reference_result(analysis)
        )
        results.append(
            _ReplayResult(
                oracle=oracle,
                analysis=analysis,
                reference_status=reference_result.status,
                reference=reference_result.reference,
            )
        )
    return tuple(results)


def test_session_02_replay_selects_true_latest_in_all_ten_frames() -> None:
    results = _replay_session()

    assert len(results) == 10
    for result in results:
        oracle = result.oracle
        analysis = result.analysis
        trace = analysis.candle_detection_trace
        assert trace is not None and trace.series_membership is not None
        membership = trace.series_membership
        final_ids = tuple(item.candidate_id for item in trace.final_candles)

        assert membership.status is CandleSeriesMembershipStatus.AVAILABLE
        assert membership.latest_candidate_id == oracle.latest_candidate_id
        assert oracle.latest_candidate_id in membership.member_candidate_ids
        assert oracle.flag_candidate_id in final_ids
        assert oracle.flag_candidate_id not in membership.member_candidate_ids
        if oracle.price_text_candidate_id is not None:
            assert oracle.price_text_candidate_id in final_ids
            assert (
                oracle.price_text_candidate_id
                not in membership.member_candidate_ids
            )
        assert analysis.series.latest is not None
        assert analysis.series.latest.candidate.x == oracle.latest_x
        assert analysis.series.latest not in analysis.series.without_latest().candles


def test_session_02_replay_removes_historical_flag_close_failures() -> None:
    results = _replay_session()

    assert all(
        result.reference_status
        is VisualPriceReferenceStatus.OK
        for result in results
    )


def test_session_02_all_entry_exit_references_are_comparable() -> None:
    grouped: dict[str, dict[str, _ReplayResult]] = {}
    for result in _replay_session():
        grouped.setdefault(result.oracle.snapshot_id, {})[
            result.oracle.phase
        ] = result

    assert len(grouped) == 5
    for pair in grouped.values():
        entry = pair["entry"].reference
        exit_reference = pair["exit"].reference
        assert entry is not None
        assert exit_reference is not None
        assert references_are_comparable(entry, exit_reference)


def test_session_02_231530_pair_has_only_closed_candle_anchors() -> None:
    results = {
        (result.oracle.snapshot_id, result.oracle.phase): result
        for result in _replay_session()
    }
    entry = results[("2026-08-17T23:15:30+00:00", "entry")]
    exit_result = results[("2026-08-17T23:15:30+00:00", "exit")]

    for result in (entry, exit_result):
        analysis = result.analysis
        trace = analysis.candle_detection_trace
        assert trace is not None and trace.series_membership is not None
        anchors = analysis.series.without_latest().candles
        anchor_ids = trace.series_membership.member_candidate_ids[:-1]

        assert len(anchors) == len(anchor_ids)
        assert result.oracle.latest_candidate_id not in anchor_ids
        assert result.oracle.flag_candidate_id not in anchor_ids
        assert result.oracle.price_text_candidate_id not in anchor_ids

    assert entry.reference is not None
    assert exit_result.reference is not None
    assert references_are_comparable(entry.reference, exit_result.reference)
