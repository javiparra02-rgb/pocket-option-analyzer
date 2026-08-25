from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import get_type_hints

import numpy as np
import pytest

from pocket_option_analyzer.application.evidence import (
    IdentityShadowEvidenceConfig,
    IdentityShadowEvidenceRecorder,
    IdentityShadowFrameEvidence,
    IdentityShadowPngMode,
    VisualEvidenceAssociation,
    VisualEvidencePhase,
    VisualFrameEvidence,
)
from pocket_option_analyzer.application.market import (
    CurrentCandleFrameContext,
    CurrentCandleIdentityEvidence,
    CurrentCandleIdentityLifecycle,
    CurrentCandleIdentityResetReason,
    CurrentCandleIdentityResolution,
    CurrentCandleIdentityResult,
    CurrentCandleIdentitySource,
    CurrentCandleIdentityStatus,
    CurrentCandleIdentityTrace,
    CurrentCandleMissingEvidence,
    TerminalSlotRegion,
)
from pocket_option_analyzer.application.strategy import (
    VisualPriceReferenceResult,
    VisualPriceReferenceStatus,
)
from pocket_option_analyzer.infrastructure.evidence import (
    FilesystemVisualEvidenceRecorder,
    IdentityShadowEvidenceReader,
    IdentityShadowEvidenceSerializer,
)
from pocket_option_analyzer.vision.models import (
    CandleCandidateDecision,
    CandleCandidateTrace,
    CandleColor,
    CandleDetectionTrace,
    CandleGeometry,
    CandleObservability,
    CandleSeries,
    CandleSeriesMembershipRunTrace,
    CandleSeriesMembershipStatus,
    CandleSeriesMembershipTrace,
    CandleType,
    ChartRegion,
    FinalCandleTrace,
    MarketAnalysis,
    TrendDirection,
)

_START = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)


def _market_analysis() -> MarketAnalysis:
    candle = FinalCandleTrace(
        candidate_id="candidate_001",
        source_candidate_ids=("candidate_001",),
        ordinal=0,
        x=50,
        y=10,
        width=8,
        height=25,
        area=200,
        color=CandleColor.WHITE,
        candle_type=CandleType.BULLISH,
        geometry=CandleGeometry(10, 14, 25, 34),
        observability=CandleObservability(
            roi_height=48,
            body_top_y=14,
            body_bottom_y=25,
            body_touches_top=False,
            body_touches_bottom=False,
        ),
        is_latest=True,
    )
    membership = CandleSeriesMembershipTrace(
        status=CandleSeriesMembershipStatus.AVAILABLE,
        evaluated_candidate_ids=(candle.candidate_id,),
        member_candidate_ids=(candle.candidate_id,),
        excluded_candidates=(),
        evaluated_gaps=(),
        estimated_pitch_px=12.0,
        candidate_runs=(
            CandleSeriesMembershipRunTrace(
                run_id="run_001",
                candidate_ids=(candle.candidate_id,),
                selected=True,
            ),
        ),
        selected_run_support=1,
        latest_candidate_id=candle.candidate_id,
        diagnostic="available_fixture",
    )
    trace = CandleDetectionTrace(
        candidates=(
            CandleCandidateTrace(
                candidate_id=candle.candidate_id,
                x=candle.x,
                y=candle.y,
                width=candle.width,
                height=candle.height,
                area=candle.area,
                color=candle.color,
                decisions=(CandleCandidateDecision.RETURNED,),
            ),
        ),
        merges=(),
        returned_candidate_ids=(candle.candidate_id,),
        dominant_width=8.0,
        maximum_returned_candidates=100,
        final_candles=(candle,),
        series_membership=membership,
    )
    return MarketAnalysis(
        series=CandleSeries(candles=()),
        trend=TrendDirection.UNKNOWN,
        candle_detection_trace=trace,
    )


def _terminal(frame_id: int) -> TerminalSlotRegion:
    return TerminalSlotRegion(
        center_x_roi=54.0,
        lower_x_roi=51.0,
        upper_x_roi=57.0,
        normalized_center_x=0.84375,
        estimated_pitch_px=12.0,
        continuity_generation=1,
        learned_from_frame_ids=(max(0, frame_id - 1), frame_id),
    )


def _resolution(
    frame_id: int,
    *,
    status: CurrentCandleIdentityStatus = CurrentCandleIdentityStatus.UNAVAILABLE,
    lifecycle: CurrentCandleIdentityLifecycle = (
        CurrentCandleIdentityLifecycle.TRACKING
    ),
    reset_reason: CurrentCandleIdentityResetReason | None = None,
    rollover_suspected: bool = False,
    rollover_confirmed: bool = False,
    session_key: str = "session-a",
    source_key: str = "win32_hwnd:123",
    identity_source: CurrentCandleIdentitySource | None = None,
) -> CurrentCandleIdentityResolution:
    confirms = status is CurrentCandleIdentityStatus.CONFIRMED
    missing = status is CurrentCandleIdentityStatus.MISSING_FROM_VIEW
    terminal = _terminal(frame_id) if confirms or missing else None
    identity_evidence = (
        CurrentCandleIdentityEvidence(
            matched_historical_member_count=3,
            type_match_ratio=1.0,
            terminal_candidate_ids=("candidate_001",),
            sufficient=True,
        )
        if confirms or missing
        else None
    )
    resolved_source = identity_source
    if resolved_source is None:
        if confirms:
            resolved_source = CurrentCandleIdentitySource.STABLE_TRACKING
        elif missing:
            resolved_source = CurrentCandleIdentitySource.TERMINAL_SLOT_EMPTY
        else:
            resolved_source = CurrentCandleIdentitySource.NONE
    result = CurrentCandleIdentityResult(
        status=status,
        candidate_id="candidate_001" if confirms else None,
        source=resolved_source,
        terminal_region=terminal,
        estimated_pitch_px=12.0,
        continuity_generation=1,
        evidence=identity_evidence,
        diagnostics=(f"fixture_{status.value}",),
    )
    trace = CurrentCandleIdentityTrace(
        frame_id=frame_id,
        wall_timestamp=_START + timedelta(seconds=frame_id),
        monotonic_timestamp=100.0 + frame_id,
        source_key=source_key,
        session_key=session_key,
        status=status,
        internal_state=lifecycle,
        continuity_generation=1,
        legacy_latest_candidate_id="candidate_001",
        terminal_region=terminal,
        estimated_pitch_px=12.0,
        sequence_match=None,
        rollover_suspected=rollover_suspected,
        rollover_confirmed=rollover_confirmed,
        chosen_candidate_id="candidate_001" if confirms else None,
        missing_evidence=(
            CurrentCandleMissingEvidence(
                terminal_region_valid=True,
                terminal_member_absent=True,
                previous_slot_candidate_id="candidate_001",
                previous_slot_fully_observable=True,
                previous_slot_distance_in_pitch_units=1.0,
                candle_like_competitor_ids=(),
            )
            if missing
            else None
        ),
        reset_reason=reset_reason,
        expiry_evidence_consistent=None,
        expiry_vertical_line_x=None,
        expiry_vertical_line_conflict=False,
        diagnostics=(f"fixture_{status.value}",),
    )
    return CurrentCandleIdentityResolution(result=result, trace=trace)


def _evidence(
    frame_id: int,
    *,
    resolution: CurrentCandleIdentityResolution | None = None,
    session_key: str = "session-a",
    source_key: str = "win32_hwnd:123",
    roi_width: int = 64,
    roi_height: int = 48,
) -> IdentityShadowFrameEvidence:
    resolved = resolution or _resolution(
        frame_id,
        session_key=session_key,
        source_key=source_key,
    )
    analysis = _market_analysis()
    detection = analysis.candle_detection_trace
    assert detection is not None
    context = CurrentCandleFrameContext(
        frame_id=frame_id,
        wall_timestamp=_START + timedelta(seconds=frame_id),
        monotonic_timestamp=100.0 + frame_id,
        roi_width=roi_width,
        roi_height=roi_height,
        source_key=source_key,
        session_key=session_key,
        membership=detection.series_membership,
        final_candles=detection.final_candles,
        overlay_evidence=detection.overlay_evidence,
    )
    return IdentityShadowFrameEvidence(
        frame_id=frame_id,
        frame_timestamp=_START + timedelta(seconds=frame_id),
        monotonic_timestamp=100.0 + frame_id,
        source_key=source_key,
        session_key=session_key,
        roi_width=roi_width,
        roi_height=roi_height,
        image=np.full(
            (roi_height, roi_width, 3),
            frame_id,
            dtype=np.uint8,
        ),
        chart_region=ChartRegion(
            x=10,
            y=20,
            width=roi_width,
            height=roi_height,
        ),
        resolution=resolved,
        frame_context=context,
        visual_price_reference_result=VisualPriceReferenceResult(
            reference=None,
            status=VisualPriceReferenceStatus.CURRENT_CLOSE_NOT_OBSERVABLE,
        ),
    )


def test_identity_config_is_conservative_and_validated() -> None:
    config = IdentityShadowEvidenceConfig()

    assert config.ring_buffer_size == 30
    assert config.pre_event_trace_count == 5
    assert config.png_mode is IdentityShadowPngMode.EVENT_ONLY
    assert config.checkpoint_interval_frames is None
    with pytest.raises(ValueError):
        IdentityShadowEvidenceConfig(
            ring_buffer_size=2,
            pre_event_trace_count=3,
        )


def test_identity_evidence_public_type_hints_resolve() -> None:
    assert get_type_hints(IdentityShadowEvidenceConfig)
    assert get_type_hints(IdentityShadowFrameEvidence)
    assert get_type_hints(IdentityShadowEvidenceRecorder.record_identity_shadow)
    assert get_type_hints(IdentityShadowEvidenceSerializer.frame_to_dict)
    assert get_type_hints(IdentityShadowEvidenceReader.read_frames)
    assert get_type_hints(FilesystemVisualEvidenceRecorder.record_identity_shadow)


def test_same_pass_model_rejects_a_different_frame() -> None:
    resolution = _resolution(2)

    with pytest.raises(ValueError, match="same frame_id"):
        _evidence(1, resolution=resolution)


def test_disabled_adapter_creates_no_identity_output(tmp_path) -> None:
    recorder = FilesystemVisualEvidenceRecorder(tmp_path)

    recorder.start_identity_session(session_key="session-a")
    recorder.record_identity_shadow(_evidence(1))
    recorder.stop_identity_session()

    assert not (tmp_path / "identity_shadow").exists()
    metadata = json.loads((tmp_path / "session_metadata.json").read_text())
    assert "identity_shadow" not in metadata


def test_enabled_session_creates_versioned_streams_and_lifecycle(tmp_path) -> None:
    recorder = FilesystemVisualEvidenceRecorder(
        tmp_path,
        identity_evidence_config=IdentityShadowEvidenceConfig(),
    )

    recorder.start_identity_session(session_key="session-a")
    recorder.stop_identity_session()

    assert (tmp_path / "identity_shadow/frames.jsonl").is_file()
    events = IdentityShadowEvidenceReader(tmp_path).read_events()
    assert [event["event_type"] for event in events] == [
        "lifecycle_start",
        "lifecycle_stop",
    ]
    metadata = json.loads((tmp_path / "session_metadata.json").read_text())
    assert metadata["identity_shadow"]["schema_version"] == 1
    assert metadata["identity_shadow"]["png_mode"] == "event_only"


def test_compact_frame_schema_is_ordered_hashed_and_replayable(tmp_path) -> None:
    recorder = FilesystemVisualEvidenceRecorder(
        tmp_path,
        identity_evidence_config=IdentityShadowEvidenceConfig(),
    )
    recorder.start_identity_session(session_key="session-a")

    recorder.record_identity_shadow(_evidence(1))
    recorder.record_identity_shadow(_evidence(2))

    frames = IdentityShadowEvidenceReader(tmp_path).read_frames()
    assert [frame["frame_id"] for frame in frames] == [1, 2]
    assert frames[0]["previous_record_sha256"] is None
    assert frames[1]["previous_record_sha256"] == frames[0]["record_sha256"]
    assert frames[0]["source_key"].startswith("sha256:")
    assert "win32_hwnd" not in json.dumps(frames[0])
    assert frames[0]["membership"]["status"] == "available"
    assert frames[0]["candles"][0]["observability"]["close_observable"]
    assert frames[0]["visual_price_reference"] == {
        "current_close_not_observable": True,
        "status": "current_close_not_observable",
    }


def test_normal_mode_writes_png_only_for_relevant_events(tmp_path) -> None:
    recorder = FilesystemVisualEvidenceRecorder(
        tmp_path,
        identity_evidence_config=IdentityShadowEvidenceConfig(),
    )
    recorder.start_identity_session(session_key="session-a")

    recorder.record_identity_shadow(_evidence(1))
    recorder.record_identity_shadow(_evidence(2))
    ambiguous = _resolution(3, status=CurrentCandleIdentityStatus.AMBIGUOUS)
    recorder.record_identity_shadow(_evidence(3, resolution=ambiguous))
    recorder.record_identity_shadow(
        _evidence(
            4,
            resolution=_resolution(
                4,
                status=CurrentCandleIdentityStatus.AMBIGUOUS,
            ),
        )
    )

    frames = IdentityShadowEvidenceReader(tmp_path).read_frames()
    assert frames[0]["png"] is None
    assert frames[1]["png"] is None
    assert frames[2]["png"]["reuses_visual_frame_evidence"] is False
    assert frames[3]["png"] is None
    assert len(tuple((tmp_path / "identity_shadow/png").glob("*.png"))) == 1
    events = IdentityShadowEvidenceReader(tmp_path).read_events()
    assert sum(event["event_type"] == "ambiguous" for event in events) == 1
    stable_events = [
        event["event_type"]
        for event in events
        if event["frame_id"] in (1, 2)
    ]
    assert stable_events == ["identity_status_changed"]


def test_event_vocabulary_covers_bootstrap_rollover_missing_and_failures(
    tmp_path,
) -> None:
    recorder = FilesystemVisualEvidenceRecorder(
        tmp_path,
        identity_evidence_config=IdentityShadowEvidenceConfig(),
    )
    recorder.start_identity_session(session_key="session-a")
    recorder.record_identity_shadow(
        _evidence(
            1,
            resolution=_resolution(
                1,
                lifecycle=CurrentCandleIdentityLifecycle.BOOTSTRAPPING,
            ),
        )
    )
    recorder.record_identity_shadow(
        _evidence(
            2,
            resolution=_resolution(
                2,
                status=CurrentCandleIdentityStatus.CONFIRMED,
                identity_source=(
                    CurrentCandleIdentitySource.BOOTSTRAP_CONFIRMATION
                ),
            ),
        )
    )
    recorder.record_identity_shadow(
        _evidence(
            3,
            resolution=_resolution(
                3,
                status=CurrentCandleIdentityStatus.CONFIRMED,
                rollover_suspected=True,
                rollover_confirmed=True,
            ),
        )
    )
    recorder.record_identity_shadow(
        _evidence(
            4,
            resolution=_resolution(
                4,
                status=CurrentCandleIdentityStatus.MISSING_FROM_VIEW,
            ),
        )
    )
    recorder.record_identity_shadow(
        _evidence(
            5,
            resolution=_resolution(
                5,
                reset_reason=CurrentCandleIdentityResetReason.INTERNAL_ERROR,
            ),
        )
    )

    event_types = {
        event["event_type"]
        for event in IdentityShadowEvidenceReader(tmp_path).read_events()
    }
    assert {
        "bootstrap_pending",
        "bootstrap_confirmed",
        "rollover_suspected",
        "rollover_confirmed",
        "missing_from_view",
        "reset",
        "resolver_failure",
    }.issubset(event_types)


def test_intensive_mode_writes_every_frame_png(tmp_path) -> None:
    recorder = FilesystemVisualEvidenceRecorder(
        tmp_path,
        identity_evidence_config=IdentityShadowEvidenceConfig(
            png_mode=IdentityShadowPngMode.ALL_FRAMES,
        ),
    )
    recorder.start_identity_session(session_key="session-a")

    recorder.record_identity_shadow(_evidence(1))
    recorder.record_identity_shadow(_evidence(2))

    assert all(
        frame["png"] is not None
        for frame in IdentityShadowEvidenceReader(tmp_path).read_frames()
    )


def test_checkpoint_is_explicit_and_not_enabled_by_default(tmp_path) -> None:
    recorder = FilesystemVisualEvidenceRecorder(
        tmp_path,
        identity_evidence_config=IdentityShadowEvidenceConfig(
            checkpoint_interval_frames=2,
        ),
    )
    recorder.start_identity_session(session_key="session-a")

    recorder.record_identity_shadow(_evidence(1))
    recorder.record_identity_shadow(_evidence(2))

    frames = IdentityShadowEvidenceReader(tmp_path).read_frames()
    events = IdentityShadowEvidenceReader(tmp_path).read_events()
    assert frames[0]["png"] is None
    assert frames[1]["png"] is not None
    assert any(event["event_type"] == "checkpoint" for event in events)


def test_ring_buffer_preserves_only_bounded_pre_event_context(tmp_path) -> None:
    recorder = FilesystemVisualEvidenceRecorder(
        tmp_path,
        identity_evidence_config=IdentityShadowEvidenceConfig(
            ring_buffer_size=2,
            pre_event_trace_count=2,
        ),
    )
    recorder.start_identity_session(session_key="session-a")
    for frame_id in (1, 2, 3):
        recorder.record_identity_shadow(_evidence(frame_id))
    recorder.record_identity_shadow(
        _evidence(
            4,
            resolution=_resolution(
                4,
                status=CurrentCandleIdentityStatus.AMBIGUOUS,
            ),
        )
    )

    event = next(
        item
        for item in IdentityShadowEvidenceReader(tmp_path).read_events()
        if item["event_type"] == "ambiguous"
    )
    assert len(event["pre_event_frame_keys"]) == 2
    assert "frame_00000002" in event["pre_event_frame_keys"][0]
    assert "frame_00000003" in event["pre_event_frame_keys"][1]


def test_multiple_events_for_one_frame_share_one_png(tmp_path) -> None:
    recorder = FilesystemVisualEvidenceRecorder(
        tmp_path,
        identity_evidence_config=IdentityShadowEvidenceConfig(),
    )
    recorder.start_identity_session(session_key="session-a")
    resolution = _resolution(
        1,
        rollover_suspected=True,
        rollover_confirmed=True,
        reset_reason=CurrentCandleIdentityResetReason.ROI_CHANGED,
    )

    recorder.record_identity_shadow(_evidence(1, resolution=resolution))

    frame_events = [
        event
        for event in IdentityShadowEvidenceReader(tmp_path).read_events()
        if event["frame_id"] == 1
    ]
    png_names = {event["png"]["filename"] for event in frame_events if event["png"]}
    assert len(frame_events) >= 4
    assert len(png_names) == 1
    assert len(tuple((tmp_path / "identity_shadow/png").glob("*.png"))) == 1


def test_stop_start_clears_ring_and_separates_sessions(tmp_path) -> None:
    recorder = FilesystemVisualEvidenceRecorder(
        tmp_path,
        identity_evidence_config=IdentityShadowEvidenceConfig(),
    )
    recorder.start_identity_session(session_key="session-a")
    recorder.record_identity_shadow(_evidence(1))
    recorder.stop_identity_session()
    recorder.start_identity_session(session_key="session-b")
    recorder.record_identity_shadow(
        _evidence(2, session_key="session-b")
    )
    recorder.stop_identity_session()

    frames = IdentityShadowEvidenceReader(tmp_path).read_frames()
    assert [frame["session_key"] for frame in frames] == [
        "session-a",
        "session-b",
    ]
    starts = [
        event
        for event in IdentityShadowEvidenceReader(tmp_path).read_events()
        if event["event_type"] == "lifecycle_start"
    ]
    assert len(starts) == 2


def test_stale_frame_is_appended_in_processing_order_without_reordering(
    tmp_path,
) -> None:
    recorder = FilesystemVisualEvidenceRecorder(
        tmp_path,
        identity_evidence_config=IdentityShadowEvidenceConfig(),
    )
    recorder.start_identity_session(session_key="session-a")
    recorder.record_identity_shadow(_evidence(2))
    stale = _resolution(
        1,
        reset_reason=CurrentCandleIdentityResetReason.FRAME_OUT_OF_ORDER,
    )
    recorder.record_identity_shadow(_evidence(1, resolution=stale))

    frames = IdentityShadowEvidenceReader(tmp_path).read_frames()
    assert [frame["sequence_number"] for frame in frames] == [1, 2]
    assert [frame["frame_id"] for frame in frames] == [2, 1]
    assert frames[1]["reset_reason"] == "frame_out_of_order"


def test_source_and_resize_resets_remain_explicit_in_frame_stream(tmp_path) -> None:
    recorder = FilesystemVisualEvidenceRecorder(
        tmp_path,
        identity_evidence_config=IdentityShadowEvidenceConfig(),
    )
    recorder.start_identity_session(session_key="session-a")
    recorder.record_identity_shadow(
        _evidence(
            1,
            resolution=_resolution(
                1,
                reset_reason=CurrentCandleIdentityResetReason.SOURCE_CHANGED,
            ),
        )
    )
    recorder.record_identity_shadow(
        _evidence(
            2,
            roi_width=80,
            roi_height=60,
            resolution=_resolution(
                2,
                reset_reason=CurrentCandleIdentityResetReason.ROI_CHANGED,
            ),
        )
    )

    frames = IdentityShadowEvidenceReader(tmp_path).read_frames()
    assert [frame["reset_reason"] for frame in frames] == [
        "source_changed",
        "roi_changed",
    ]
    assert frames[1]["roi"]["previous"]["width"] == 64
    assert frames[1]["roi"]["previous"]["height"] == 48
    assert frames[1]["roi"]["current"]["width"] == 80
    assert frames[1]["roi"]["current"]["height"] == 60


def test_png_failure_is_logged_and_does_not_escape(tmp_path) -> None:
    def fail_encoding(_image: np.ndarray) -> bytes:
        raise OSError("disk unavailable")

    recorder = FilesystemVisualEvidenceRecorder(
        tmp_path,
        identity_evidence_config=IdentityShadowEvidenceConfig(
            png_mode=IdentityShadowPngMode.ALL_FRAMES,
        ),
        png_encoder=fail_encoding,
    )
    recorder.start_identity_session(session_key="session-a")

    recorder.record_identity_shadow(_evidence(1))

    assert IdentityShadowEvidenceReader(tmp_path).read_frames() == ()
    failures = [
        json.loads(line)
        for line in (tmp_path / "failures.jsonl").read_text().splitlines()
        if line
    ]
    assert failures[-1]["stage"] == "record_identity_shadow"
    assert any(
        event["event_type"] == "persistence_failure"
        for event in IdentityShadowEvidenceReader(tmp_path).read_events()
    )
    assert not tuple((tmp_path / "identity_shadow/png").glob("*.tmp"))


def test_existing_visual_frame_png_is_reused_without_duplicate_bytes(tmp_path) -> None:
    recorder = FilesystemVisualEvidenceRecorder(
        tmp_path,
        identity_evidence_config=IdentityShadowEvidenceConfig(
            png_mode=IdentityShadowPngMode.ALL_FRAMES,
        ),
    )
    identity = _evidence(1)
    analysis = _market_analysis()
    frame = VisualFrameEvidence(
        frame_id=identity.frame_id,
        frame_timestamp=identity.frame_timestamp,
        image=identity.image,
        price_observation_image=None,
        chart_region=identity.chart_region,
        price_observation_region=None,
        source="test",
        market_analysis=analysis,
        current_visual_price=analysis.current_visual_price,
        visual_price_reference_result=identity.visual_price_reference_result,
        candle_detection_trace=(
            analysis.candle_detection_trace
        ),
        current_visual_price_detection_trace=(
            analysis.current_visual_price_detection_trace
        ),
    )
    association = VisualEvidenceAssociation(
        snapshot_id=_START.isoformat(),
        phase=VisualEvidencePhase.ENTRY,
        observed_at=_START,
        resolve_at=_START + timedelta(minutes=1),
        candle_interval_started_at=_START,
    )
    recorder.record_frame(frame, (association,))
    recorder.start_identity_session(session_key="session-a")

    recorder.record_identity_shadow(identity)

    persisted = IdentityShadowEvidenceReader(tmp_path).read_frames()[0]
    assert persisted["png"]["reuses_visual_frame_evidence"] is True
    assert not tuple((tmp_path / "identity_shadow/png").glob("*.png"))


def test_reader_rejects_tampered_frame_payload(tmp_path) -> None:
    recorder = FilesystemVisualEvidenceRecorder(
        tmp_path,
        identity_evidence_config=IdentityShadowEvidenceConfig(),
    )
    recorder.start_identity_session(session_key="session-a")
    recorder.record_identity_shadow(_evidence(1))
    path = tmp_path / "identity_shadow/frames.jsonl"
    payload = json.loads(path.read_text())
    payload["frame_id"] = 999
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="hash does not match"):
        IdentityShadowEvidenceReader(tmp_path).read_frames()


def test_restart_loads_hash_chains_and_rejects_duplicate_frame(tmp_path) -> None:
    config = IdentityShadowEvidenceConfig()
    first = FilesystemVisualEvidenceRecorder(
        tmp_path,
        identity_evidence_config=config,
    )
    first.start_identity_session(session_key="session-a")
    first.record_identity_shadow(_evidence(1))
    first.stop_identity_session()

    restarted = FilesystemVisualEvidenceRecorder(
        tmp_path,
        identity_evidence_config=config,
    )
    restarted.start_identity_session(session_key="session-a")
    restarted.record_identity_shadow(_evidence(1))

    assert len(IdentityShadowEvidenceReader(tmp_path).read_frames()) == 1
    failures = (tmp_path / "failures.jsonl").read_text()
    assert "Duplicate identity frame evidence" in failures


def test_existing_session_metadata_is_extended_only_when_opted_in(tmp_path) -> None:
    FilesystemVisualEvidenceRecorder(tmp_path)
    before = json.loads((tmp_path / "session_metadata.json").read_text())
    assert "identity_shadow" not in before

    FilesystemVisualEvidenceRecorder(
        tmp_path,
        identity_evidence_config=IdentityShadowEvidenceConfig(),
    )

    after = json.loads((tmp_path / "session_metadata.json").read_text())
    assert after["identity_shadow"]["enabled"] is True
    assert after["identity_shadow"]["post_event_frames"] == 0


def test_expiry_vertical_extent_is_preserved_in_runtime_trace() -> None:
    resolution = _resolution(1)
    trace = replace(
        resolution.trace,
        expiry_vertical_line_x=700,
        expiry_vertical_line_start_y=100,
        expiry_vertical_line_end_y=740,
    )

    assert trace.expiry_vertical_line_x == 700
    assert trace.expiry_vertical_line_start_y == 100
    assert trace.expiry_vertical_line_end_y == 740
