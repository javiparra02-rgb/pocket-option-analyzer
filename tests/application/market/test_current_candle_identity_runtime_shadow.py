from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import get_type_hints

import pytest

from pocket_option_analyzer.application.market import (
    CurrentCandleIdentityFrameContextBuilder,
    CurrentCandleIdentityFrameMetadata,
    CurrentCandleIdentityLifecycle,
    CurrentCandleIdentityResetReason,
    CurrentCandleIdentityResolver,
    CurrentCandleIdentityRuntimeShadow,
    CurrentCandleIdentityStatus,
)
from pocket_option_analyzer.vision.models import (
    CandleCandidateDecision,
    CandleCandidateTrace,
    CandleColor,
    CandleDetectionTrace,
    CandleGeometry,
    CandleObservability,
    CandleOverlayEvidence,
    CandleOverlayEvidenceStatus,
    CandleOverlayEvidenceTrace,
    CandleSeries,
    CandleSeriesMembershipRunTrace,
    CandleSeriesMembershipStatus,
    CandleSeriesMembershipTrace,
    CandleType,
    FinalCandleTrace,
    MarketAnalysis,
    TrendDirection,
)

_START = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)


def _final_candles(
    *,
    frame_id: int,
    candle_types: tuple[CandleType, ...],
) -> tuple[FinalCandleTrace, ...]:
    candles = []
    for index, candle_type in enumerate(candle_types):
        candidate_id = f"frame{frame_id}_candidate{index}"
        body_top = 103 + index
        body_bottom = 111 + index
        candles.append(
            FinalCandleTrace(
                candidate_id=candidate_id,
                source_candidate_ids=(candidate_id,),
                ordinal=index,
                x=100 + 12 * index,
                y=100 + index,
                width=8,
                height=18,
                area=144,
                color=(
                    CandleColor.WHITE
                    if candle_type is CandleType.BULLISH
                    else CandleColor.RED
                ),
                candle_type=candle_type,
                geometry=CandleGeometry(
                    high_y=100 + index,
                    body_top_y=body_top,
                    body_bottom_y=body_bottom,
                    low_y=117 + index,
                ),
                observability=CandleObservability(
                    roi_height=788,
                    body_top_y=body_top,
                    body_bottom_y=body_bottom,
                    body_touches_top=False,
                    body_touches_bottom=False,
                ),
                is_latest=index == len(candle_types) - 1,
            )
        )
    return tuple(candles)


def _membership(
    candles: tuple[FinalCandleTrace, ...],
) -> CandleSeriesMembershipTrace:
    candidate_ids = tuple(candle.candidate_id for candle in candles)
    return CandleSeriesMembershipTrace(
        status=CandleSeriesMembershipStatus.AVAILABLE,
        evaluated_candidate_ids=candidate_ids,
        member_candidate_ids=candidate_ids,
        excluded_candidates=(),
        evaluated_gaps=(),
        estimated_pitch_px=12.0,
        candidate_runs=(
            CandleSeriesMembershipRunTrace(
                run_id="selected",
                candidate_ids=candidate_ids,
                selected=True,
            ),
        ),
        selected_run_support=len(candidate_ids),
        latest_candidate_id=candidate_ids[-1],
        diagnostic="available_fixture",
    )


def _overlay(
    candles: tuple[FinalCandleTrace, ...],
    *,
    overlay_indices: tuple[int, ...] = (),
) -> CandleOverlayEvidenceTrace:
    evidence = tuple(
        CandleOverlayEvidence(
            candidate_id=candle.candidate_id,
            status=(
                CandleOverlayEvidenceStatus.EXPIRY_OVERLAY
                if index in overlay_indices
                else CandleOverlayEvidenceStatus.NO_EVIDENCE
            ),
            vertical_line_support_ratio=0.75,
            contact_gap_ratio=0.0,
            horizontal_alignment_ratio=0.0,
            cap_height_to_width_ratio=0.5,
            wickless=index in overlay_indices,
            diagnostic=(
                "cap_attached_to_long_vertical_line"
                if index in overlay_indices
                else "expiry_overlay_structure_not_detected"
            ),
            vertical_line_x=(700 + index if index in overlay_indices else None),
            vertical_line_start_y=(100 if index in overlay_indices else None),
            vertical_line_end_y=(700 if index in overlay_indices else None),
        )
        for index, candle in enumerate(candles)
    )
    return CandleOverlayEvidenceTrace(
        evaluated_candidate_ids=tuple(candle.candidate_id for candle in candles),
        evidence=evidence,
    )


def _market_analysis(
    *,
    frame_id: int,
    candle_types: tuple[CandleType, ...],
    overlay_indices: tuple[int, ...] = (),
    membership_available: bool = True,
) -> MarketAnalysis:
    candles = _final_candles(frame_id=frame_id, candle_types=candle_types)
    candidate_ids = tuple(candle.candidate_id for candle in candles)
    trace = CandleDetectionTrace(
        candidates=tuple(
            CandleCandidateTrace(
                candidate_id=candle.candidate_id,
                x=candle.x,
                y=candle.y,
                width=candle.width,
                height=candle.height,
                area=candle.area,
                color=candle.color,
                decisions=(CandleCandidateDecision.RETURNED,),
            )
            for candle in candles
        ),
        merges=(),
        returned_candidate_ids=candidate_ids,
        dominant_width=8.0,
        maximum_returned_candidates=100,
        final_candles=candles,
        series_membership=(
            _membership(candles) if membership_available else None
        ),
        overlay_evidence=_overlay(candles, overlay_indices=overlay_indices),
    )
    return MarketAnalysis(
        series=CandleSeries(candles=()),
        trend=TrendDirection.UNKNOWN,
        candle_detection_trace=trace,
    )


def _metadata(frame_id: int, *, source_key: str = "win32_hwnd:123"):
    return CurrentCandleIdentityFrameMetadata(
        frame_id=frame_id,
        wall_timestamp=_START + timedelta(seconds=frame_id),
        monotonic_timestamp=100.0 + frame_id,
        source_key=source_key,
        session_key="session-a",
        roi_width=1000,
        roi_height=788,
    )


def _tracking_shadow() -> tuple[
    CurrentCandleIdentityRuntimeShadow,
    tuple[CandleType, ...],
]:
    shadow = CurrentCandleIdentityRuntimeShadow(
        resolver=CurrentCandleIdentityResolver()
    )
    initial_types = (
        CandleType.BULLISH,
        CandleType.BEARISH,
        CandleType.BULLISH,
        CandleType.BEARISH,
        CandleType.BULLISH,
        CandleType.BEARISH,
        CandleType.BULLISH,
    )
    rollover_types = (*initial_types[1:], CandleType.BEARISH)
    shadow.start_session(session_key="session-a")
    for frame_id, candle_types in (
        (1, initial_types),
        (2, rollover_types),
        (3, rollover_types),
    ):
        shadow.resolve(
            metadata=_metadata(frame_id),
            market_analysis=_market_analysis(
                frame_id=frame_id,
                candle_types=candle_types,
            ),
        )
    return shadow, rollover_types


def test_context_builder_reuses_exact_same_pass_trace_objects() -> None:
    analysis = _market_analysis(
        frame_id=1,
        candle_types=(CandleType.BULLISH, CandleType.BEARISH),
        overlay_indices=(1,),
    )
    trace = analysis.candle_detection_trace
    assert trace is not None

    context = CurrentCandleIdentityFrameContextBuilder().build(
        metadata=_metadata(1),
        market_analysis=analysis,
    )

    assert context.membership is trace.series_membership
    assert context.final_candles is trace.final_candles
    assert context.overlay_evidence is trace.overlay_evidence
    assert context.expiry_vertical_line_x == 701
    assert context.expiry_vertical_line_conflict is False


def test_context_builder_reports_conflicting_expiry_lines_conservatively() -> None:
    analysis = _market_analysis(
        frame_id=1,
        candle_types=(CandleType.BULLISH, CandleType.BEARISH),
        overlay_indices=(0, 1),
    )

    context = CurrentCandleIdentityFrameContextBuilder().build(
        metadata=_metadata(1),
        market_analysis=analysis,
    )

    assert context.expiry_vertical_line_x is None
    assert context.expiry_vertical_line_conflict is True


def test_runtime_shadow_bootstraps_across_one_real_session() -> None:
    shadow = CurrentCandleIdentityRuntimeShadow(
        resolver=CurrentCandleIdentityResolver()
    )
    initial_types = (
        CandleType.BULLISH,
        CandleType.BEARISH,
        CandleType.BULLISH,
        CandleType.BEARISH,
        CandleType.BULLISH,
        CandleType.BEARISH,
        CandleType.BULLISH,
    )
    rollover_types = (*initial_types[1:], CandleType.BEARISH)
    shadow.start_session(session_key="session-a")

    first = shadow.resolve(
        metadata=_metadata(1),
        market_analysis=_market_analysis(frame_id=1, candle_types=initial_types),
    )
    second = shadow.resolve(
        metadata=_metadata(2),
        market_analysis=_market_analysis(frame_id=2, candle_types=rollover_types),
    )
    third = shadow.resolve(
        metadata=_metadata(3),
        market_analysis=_market_analysis(frame_id=3, candle_types=rollover_types),
    )

    assert first.result.status is CurrentCandleIdentityStatus.UNAVAILABLE
    assert second.result.status is CurrentCandleIdentityStatus.UNAVAILABLE
    assert third.result.status is CurrentCandleIdentityStatus.CONFIRMED
    assert shadow.last_resolution is third
    assert third.trace.wall_timestamp == _metadata(3).wall_timestamp
    assert third.trace.monotonic_timestamp == 103.0
    assert third.trace.source_key == "win32_hwnd:123"
    assert third.trace.session_key == "session-a"


def test_runtime_shadow_stop_and_restart_clear_temporal_continuity() -> None:
    shadow = CurrentCandleIdentityRuntimeShadow(
        resolver=CurrentCandleIdentityResolver()
    )
    analysis = _market_analysis(
        frame_id=1,
        candle_types=(
            CandleType.BULLISH,
            CandleType.BEARISH,
            CandleType.BULLISH,
        ),
    )
    shadow.start_session(session_key="session-a")
    first = shadow.resolve(metadata=_metadata(1), market_analysis=analysis)
    shadow.stop_session()

    assert shadow.session_key is None
    assert shadow.last_resolution is first

    shadow.start_session(session_key="session-b")
    restarted = shadow.resolve(
        metadata=CurrentCandleIdentityFrameMetadata(
            frame_id=2,
            wall_timestamp=_START + timedelta(seconds=2),
            monotonic_timestamp=102.0,
            source_key="win32_hwnd:123",
            session_key="session-b",
            roi_width=1000,
            roi_height=788,
        ),
        market_analysis=_market_analysis(
            frame_id=2,
            candle_types=(
                CandleType.BULLISH,
                CandleType.BEARISH,
                CandleType.BULLISH,
            ),
        ),
    )

    assert restarted.result.status is CurrentCandleIdentityStatus.UNAVAILABLE
    assert restarted.result.continuity_generation > (
        first.result.continuity_generation
    )
    assert restarted.result.terminal_region is None
    assert restarted.trace.reset_reason is None
    assert restarted.trace.internal_state is (
        CurrentCandleIdentityLifecycle.BOOTSTRAPPING
    )


def test_runtime_shadow_source_change_is_visible_and_non_conclusive() -> None:
    shadow, types = _tracking_shadow()

    changed = shadow.resolve(
        metadata=_metadata(4, source_key="win32_hwnd:999"),
        market_analysis=_market_analysis(frame_id=4, candle_types=types),
    )

    assert changed.result.status is CurrentCandleIdentityStatus.UNAVAILABLE
    assert changed.trace.reset_reason is CurrentCandleIdentityResetReason.SOURCE_CHANGED
    assert changed.trace.source_key == "win32_hwnd:999"


def test_runtime_shadow_roi_resize_resets_without_asserting_identity() -> None:
    shadow, types = _tracking_shadow()
    resized_metadata = CurrentCandleIdentityFrameMetadata(
        frame_id=4,
        wall_timestamp=_START + timedelta(seconds=4),
        monotonic_timestamp=104.0,
        source_key="win32_hwnd:123",
        session_key="session-a",
        roi_width=1200,
        roi_height=900,
    )

    resized = shadow.resolve(
        metadata=resized_metadata,
        market_analysis=_market_analysis(frame_id=4, candle_types=types),
    )

    assert resized.result.status is CurrentCandleIdentityStatus.UNAVAILABLE
    assert resized.trace.reset_reason is CurrentCandleIdentityResetReason.ROI_CHANGED


def test_runtime_shadow_membership_unavailable_is_non_conclusive() -> None:
    shadow = CurrentCandleIdentityRuntimeShadow(
        resolver=CurrentCandleIdentityResolver()
    )
    shadow.start_session(session_key="session-a")

    resolution = shadow.resolve(
        metadata=_metadata(1),
        market_analysis=_market_analysis(
            frame_id=1,
            candle_types=(CandleType.BULLISH, CandleType.BEARISH),
            membership_available=False,
        ),
    )

    assert resolution.result.status is CurrentCandleIdentityStatus.UNAVAILABLE
    assert resolution.trace.internal_state is CurrentCandleIdentityLifecycle.DEGRADED


def test_stale_frame_does_not_replace_last_committed_resolver_trace() -> None:
    shadow = CurrentCandleIdentityRuntimeShadow(
        resolver=CurrentCandleIdentityResolver()
    )
    types = (CandleType.BULLISH, CandleType.BEARISH, CandleType.BULLISH)
    shadow.start_session(session_key="session-a")
    first = shadow.resolve(
        metadata=_metadata(1),
        market_analysis=_market_analysis(frame_id=1, candle_types=types),
    )

    stale = shadow.resolve(
        metadata=_metadata(1),
        market_analysis=_market_analysis(frame_id=1, candle_types=types),
    )

    assert stale.result.status is CurrentCandleIdentityStatus.UNAVAILABLE
    assert stale.trace.reset_reason is (
        CurrentCandleIdentityResetReason.FRAME_OUT_OF_ORDER
    )
    assert shadow.resolver.last_trace is first.trace
    assert shadow.last_resolution is stale


class _InvariantFailureResolver:
    def start_session(self, *, source_key: str, session_key: str) -> None:
        pass

    def stop_session(self) -> None:
        pass

    def resolve_with_trace(self, *, frame_context):
        raise TypeError("program invariant")


class _OperationalFailureResolver:
    def __init__(self) -> None:
        self.lifecycle = CurrentCandleIdentityLifecycle.BOOTSTRAPPING
        self.continuity_generation = 0

    def start_session(self, *, source_key: str, session_key: str) -> None:
        self.continuity_generation += 1

    def stop_session(self) -> None:
        self.continuity_generation += 1

    def reset(self, reason: CurrentCandleIdentityResetReason) -> None:
        assert reason is CurrentCandleIdentityResetReason.INTERNAL_ERROR
        self.continuity_generation += 1

    def resolve_with_trace(self, *, frame_context):
        raise OSError("operational failure")


def test_runtime_shadow_isolates_operational_failure_as_unavailable() -> None:
    resolver = _OperationalFailureResolver()
    shadow = CurrentCandleIdentityRuntimeShadow(
        resolver=resolver,  # type: ignore[arg-type]
    )
    shadow.start_session(session_key="session-a")

    resolution = shadow.resolve(
        metadata=_metadata(1),
        market_analysis=_market_analysis(
            frame_id=1,
            candle_types=(CandleType.BULLISH, CandleType.BEARISH),
        ),
    )

    assert resolution.result.status is CurrentCandleIdentityStatus.UNAVAILABLE
    assert resolution.trace.reset_reason is (
        CurrentCandleIdentityResetReason.INTERNAL_ERROR
    )
    assert resolution.result.diagnostics == (
        "runtime_shadow_operational_error:OSError",
    )
    assert shadow.last_resolution is resolution


def test_runtime_shadow_does_not_hide_program_invariant_failures() -> None:
    shadow = CurrentCandleIdentityRuntimeShadow(
        resolver=_InvariantFailureResolver(),  # type: ignore[arg-type]
    )
    shadow.start_session(session_key="session-a")

    with pytest.raises(TypeError, match="program invariant"):
        shadow.resolve(
            metadata=_metadata(1),
            market_analysis=_market_analysis(
                frame_id=1,
                candle_types=(CandleType.BULLISH, CandleType.BEARISH),
            ),
        )


def test_runtime_shadow_public_contracts_resolve_runtime_type_hints() -> None:
    for contract in (
        CurrentCandleIdentityFrameMetadata,
        CurrentCandleIdentityFrameContextBuilder.build,
        CurrentCandleIdentityRuntimeShadow.start_session,
        CurrentCandleIdentityRuntimeShadow.stop_session,
        CurrentCandleIdentityRuntimeShadow.resolve,
    ):
        assert get_type_hints(contract)
