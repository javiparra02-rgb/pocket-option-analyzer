from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from threading import Thread

import pytest

from pocket_option_analyzer.application.market import (
    CurrentCandleFrameContext,
    CurrentCandleIdentityConfig,
    CurrentCandleIdentityLifecycle,
    CurrentCandleIdentityMatcher,
    CurrentCandleIdentityResetReason,
    CurrentCandleIdentityResolver,
    CurrentCandleIdentitySource,
    CurrentCandleIdentityStatus,
)
from pocket_option_analyzer.vision.models import (
    CandleColor,
    CandleGeometry,
    CandleObservability,
    CandleOverlayEvidence,
    CandleOverlayEvidenceStatus,
    CandleOverlayEvidenceTrace,
    CandleSeriesMembershipExclusion,
    CandleSeriesMembershipExclusionReason,
    CandleSeriesMembershipRunTrace,
    CandleSeriesMembershipStatus,
    CandleSeriesMembershipTrace,
    CandleType,
    FinalCandleTrace,
)

_START = datetime(2026, 8, 24, tzinfo=UTC)


def _types(count: int) -> tuple[CandleType, ...]:
    return tuple(
        CandleType.BULLISH if index % 2 == 0 else CandleType.BEARISH
        for index in range(count)
    )


def _candles(
    candle_types: tuple[CandleType, ...],
    *,
    frame: int,
    pitch: int = 12,
    start_x: int = 100,
    roi_height: int = 788,
    terminal_close_clipped: bool = False,
) -> tuple[FinalCandleTrace, ...]:
    candles: list[FinalCandleTrace] = []
    for index, candle_type in enumerate(candle_types):
        high_y = 100 + index
        body_top_y = high_y + 3
        body_bottom_y = high_y + 11
        low_y = high_y + 17
        if terminal_close_clipped and index == len(candle_types) - 1:
            candle_type = CandleType.BEARISH
            body_bottom_y = roi_height - 1
            low_y = roi_height - 1
        geometry = CandleGeometry(
            high_y=high_y,
            body_top_y=body_top_y,
            body_bottom_y=body_bottom_y,
            low_y=low_y,
        )
        observability = CandleObservability(
            roi_height=roi_height,
            body_top_y=body_top_y,
            body_bottom_y=body_bottom_y,
            body_touches_top=body_top_y == 0,
            body_touches_bottom=body_bottom_y == roi_height - 1,
        )
        candles.append(
            FinalCandleTrace(
                candidate_id=f"frame{frame}_candidate{index}",
                source_candidate_ids=(f"source{frame}_{index}",),
                ordinal=index,
                x=start_x + index * pitch,
                y=high_y,
                width=8,
                height=low_y - high_y + 1,
                area=8 * (low_y - high_y + 1),
                color=(
                    CandleColor.WHITE
                    if candle_type is CandleType.BULLISH
                    else CandleColor.RED
                ),
                candle_type=candle_type,
                geometry=geometry,
                observability=observability,
                is_latest=index == len(candle_types) - 1,
            )
        )
    return tuple(candles)


def _membership(
    members: tuple[FinalCandleTrace, ...],
    *,
    pitch: float = 12.0,
    excluded: tuple[FinalCandleTrace, ...] = (),
) -> CandleSeriesMembershipTrace:
    member_ids = tuple(candle.candidate_id for candle in members)
    excluded_ids = tuple(candle.candidate_id for candle in excluded)
    return CandleSeriesMembershipTrace(
        status=CandleSeriesMembershipStatus.AVAILABLE,
        evaluated_candidate_ids=(*member_ids, *excluded_ids),
        member_candidate_ids=member_ids,
        excluded_candidates=tuple(
            CandleSeriesMembershipExclusion(
                candidate_id=candidate_id,
                reason=CandleSeriesMembershipExclusionReason.EXPIRY_OVERLAY,
                diagnostic="fixture_expiry_overlay",
            )
            for candidate_id in excluded_ids
        ),
        evaluated_gaps=(),
        estimated_pitch_px=pitch,
        candidate_runs=(
            CandleSeriesMembershipRunTrace(
                run_id="selected",
                candidate_ids=member_ids,
                selected=True,
            ),
            *tuple(
                CandleSeriesMembershipRunTrace(
                    run_id=f"excluded_{index}",
                    candidate_ids=(candidate_id,),
                    selected=False,
                )
                for index, candidate_id in enumerate(excluded_ids)
            ),
        ),
        selected_run_support=len(member_ids),
        latest_candidate_id=member_ids[-1],
        diagnostic="available_fixture",
    )


def _context(
    *,
    frame: int,
    members: tuple[FinalCandleTrace, ...],
    pitch: float = 12.0,
    roi_width: int = 1000,
    roi_height: int = 788,
    source_key: str = "source-a",
    session_key: str = "session-a",
    final_extras: tuple[FinalCandleTrace, ...] = (),
    overlay_evidence: CandleOverlayEvidenceTrace | None = None,
    expiry_evidence_consistent: bool | None = None,
    membership_available: bool = True,
    monotonic_timestamp: float | None = None,
    wall_timestamp: datetime | None = None,
) -> CurrentCandleFrameContext:
    return CurrentCandleFrameContext(
        frame_id=frame,
        wall_timestamp=wall_timestamp or _START + timedelta(seconds=frame),
        monotonic_timestamp=(
            float(frame) if monotonic_timestamp is None else monotonic_timestamp
        ),
        roi_width=roi_width,
        roi_height=roi_height,
        source_key=source_key,
        session_key=session_key,
        membership=(
            _membership(members, pitch=pitch, excluded=final_extras)
            if membership_available
            else None
        ),
        final_candles=(*members, *final_extras),
        overlay_evidence=overlay_evidence,
        expiry_evidence_consistent=expiry_evidence_consistent,
    )


def _bootstrap_frames(
    *,
    count: int = 7,
    pitch: int = 12,
    clipped_third_terminal: bool = False,
) -> tuple[CurrentCandleFrameContext, ...]:
    first_types = _types(count)
    rollover_types = (*first_types[1:], CandleType.BEARISH)
    return (
        _context(
            frame=1,
            members=_candles(first_types, frame=1, pitch=pitch),
            pitch=float(pitch),
        ),
        _context(
            frame=2,
            members=_candles(rollover_types, frame=2, pitch=pitch),
            pitch=float(pitch),
        ),
        _context(
            frame=3,
            members=_candles(
                rollover_types,
                frame=3,
                pitch=pitch,
                terminal_close_clipped=clipped_third_terminal,
            ),
            pitch=float(pitch),
        ),
    )


def _tracking_resolver(
    *,
    count: int = 7,
    clipped_third_terminal: bool = False,
) -> tuple[
    CurrentCandleIdentityResolver,
    tuple[CandleType, ...],
]:
    resolver = CurrentCandleIdentityResolver()
    frames = _bootstrap_frames(
        count=count,
        clipped_third_terminal=clipped_third_terminal,
    )
    assert resolver.resolve(frame_context=frames[0]).status is (
        CurrentCandleIdentityStatus.UNAVAILABLE
    )
    assert resolver.resolve(frame_context=frames[1]).status is (
        CurrentCandleIdentityStatus.UNAVAILABLE
    )
    assert resolver.resolve(frame_context=frames[2]).status is (
        CurrentCandleIdentityStatus.CONFIRMED
    )
    return resolver, tuple(candle.candle_type for candle in frames[2].member_candles)


def test_initial_frame_is_unavailable_and_rightmost_alone_does_not_bootstrap() -> None:
    resolver = CurrentCandleIdentityResolver()
    first = _bootstrap_frames()[0]

    resolution = resolver.resolve_with_trace(frame_context=first)

    assert resolution.result.status is CurrentCandleIdentityStatus.UNAVAILABLE
    assert resolution.result.candidate_id is None
    assert resolution.result.terminal_region is None
    assert resolution.trace.internal_state is (
        CurrentCandleIdentityLifecycle.BOOTSTRAPPING
    )
    assert resolution.trace.legacy_latest_candidate_id == (
        first.member_candles[-1].candidate_id
    )


def test_trusted_rollover_remains_pending_until_stable_third_frame() -> None:
    resolver = CurrentCandleIdentityResolver()
    first, rollover, stable = _bootstrap_frames()

    resolver.resolve(frame_context=first)
    pending = resolver.resolve_with_trace(frame_context=rollover)
    confirmed = resolver.resolve_with_trace(frame_context=stable)

    assert pending.result.status is CurrentCandleIdentityStatus.UNAVAILABLE
    assert pending.trace.rollover_suspected is True
    assert pending.trace.rollover_confirmed is False
    assert pending.trace.terminal_region is not None
    assert confirmed.result.status is CurrentCandleIdentityStatus.CONFIRMED
    assert confirmed.result.candidate_id == stable.member_candles[-1].candidate_id
    assert confirmed.result.source is CurrentCandleIdentitySource.BOOTSTRAP_CONFIRMATION
    assert confirmed.trace.internal_state is CurrentCandleIdentityLifecycle.TRACKING
    assert confirmed.trace.rollover_confirmed is True
    assert confirmed.result.terminal_region is not None
    assert confirmed.result.terminal_region.learned_from_frame_ids == (1, 2, 3)


def test_stable_tracking_confirms_same_frame_terminal_candidate() -> None:
    resolver, current_types = _tracking_resolver()
    frame = _context(frame=4, members=_candles(current_types, frame=4))

    result = resolver.resolve(frame_context=frame)

    assert result.status is CurrentCandleIdentityStatus.CONFIRMED
    assert result.candidate_id == frame.member_candles[-1].candidate_id
    assert result.source is CurrentCandleIdentitySource.STABLE_TRACKING


def test_current_disappears_from_learned_terminal_and_previous_is_observable() -> None:
    resolver, current_types = _tracking_resolver()
    frame = _context(frame=4, members=_candles(current_types[:-1], frame=4))

    resolution = resolver.resolve_with_trace(frame_context=frame)

    assert resolution.result.status is CurrentCandleIdentityStatus.MISSING_FROM_VIEW
    assert resolution.result.candidate_id is None
    assert resolution.result.source is CurrentCandleIdentitySource.TERMINAL_SLOT_EMPTY
    assert resolution.trace.missing_evidence is not None
    assert resolution.trace.missing_evidence.previous_slot_fully_observable is True
    assert resolution.trace.missing_evidence.sufficient is True


def test_fully_observable_previous_candle_is_not_promoted_to_current() -> None:
    resolver, current_types = _tracking_resolver()
    frame = _context(frame=4, members=_candles(current_types[:-1], frame=4))

    result = resolver.resolve(frame_context=frame)

    assert result.status is CurrentCandleIdentityStatus.MISSING_FROM_VIEW
    assert result.candidate_id is None
    assert frame.membership is not None
    assert frame.membership.latest_candidate_id != result.candidate_id


@pytest.mark.parametrize("member_count", [27, 28])
def test_member_count_has_no_special_missing_semantics(member_count: int) -> None:
    resolver, current_types = _tracking_resolver(count=member_count)
    frame = _context(frame=4, members=_candles(current_types, frame=4))

    result = resolver.resolve(frame_context=frame)

    assert result.status is CurrentCandleIdentityStatus.CONFIRMED
    assert result.candidate_id == frame.member_candles[-1].candidate_id


def test_candidate_ids_change_every_frame_without_breaking_identity() -> None:
    resolver = CurrentCandleIdentityResolver()
    first, second, third = _bootstrap_frames()

    results = tuple(
        resolver.resolve(frame_context=context) for context in (first, second, third)
    )

    assert first.membership is not None
    assert second.membership is not None
    assert set(first.membership.member_candidate_ids).isdisjoint(
        second.membership.member_candidate_ids
    )
    assert results[-1].candidate_id == third.member_candles[-1].candidate_id


def test_bad_type_alignment_does_not_create_trusted_rollover() -> None:
    resolver = CurrentCandleIdentityResolver()
    first = _bootstrap_frames()[0]
    bad = _context(
        frame=2,
        members=_candles((CandleType.DOJI,) * 7, frame=2),
    )

    resolver.resolve(frame_context=first)
    resolution = resolver.resolve_with_trace(frame_context=bad)

    assert resolution.result.status is CurrentCandleIdentityStatus.UNAVAILABLE
    assert resolution.trace.rollover_suspected is False


def test_pitch_jump_resets_tracking_without_recalibrating_in_place() -> None:
    resolver, current_types = _tracking_resolver()
    frame = _context(
        frame=4,
        members=_candles(current_types, frame=4, pitch=16),
        pitch=16.0,
    )
    generation = resolver.continuity_generation

    resolution = resolver.resolve_with_trace(frame_context=frame)

    assert resolution.result.status is CurrentCandleIdentityStatus.UNAVAILABLE
    assert resolution.trace.reset_reason is (
        CurrentCandleIdentityResetReason.PITCH_DISCONTINUITY
    )
    assert resolver.continuity_generation == generation + 1


def test_material_roi_resize_resets_tracking_without_remapping_region() -> None:
    resolver, current_types = _tracking_resolver()
    frame = _context(
        frame=4,
        members=_candles(current_types, frame=4),
        roi_width=1100,
    )

    resolution = resolver.resolve_with_trace(frame_context=frame)

    assert resolution.result.status is CurrentCandleIdentityStatus.UNAVAILABLE
    assert resolution.result.terminal_region is None
    assert resolution.trace.reset_reason is CurrentCandleIdentityResetReason.ROI_CHANGED


def test_stale_frame_does_not_mutate_committed_state() -> None:
    resolver, current_types = _tracking_resolver()
    generation = resolver.continuity_generation
    committed_trace = resolver.last_trace
    stale = _context(frame=3, members=_candles(current_types, frame=30))

    resolution = resolver.resolve_with_trace(frame_context=stale)

    assert resolution.result.status is CurrentCandleIdentityStatus.UNAVAILABLE
    assert resolution.trace.reset_reason is (
        CurrentCandleIdentityResetReason.FRAME_OUT_OF_ORDER
    )
    assert resolver.continuity_generation == generation
    assert resolver.last_trace is committed_trace

    valid = _context(frame=4, members=_candles(current_types, frame=4))
    assert resolver.resolve(frame_context=valid).status is (
        CurrentCandleIdentityStatus.CONFIRMED
    )


def test_monotonic_time_regression_is_rejected_without_state_mutation() -> None:
    resolver, current_types = _tracking_resolver()
    generation = resolver.continuity_generation
    frame = _context(
        frame=4,
        members=_candles(current_types, frame=4),
        monotonic_timestamp=2.5,
    )

    resolution = resolver.resolve_with_trace(frame_context=frame)

    assert resolution.trace.reset_reason is (
        CurrentCandleIdentityResetReason.TIME_REGRESSION
    )
    assert resolver.continuity_generation == generation


def test_source_change_resets_and_rebootstraps_without_crossing_identity() -> None:
    resolver, current_types = _tracking_resolver()
    generation = resolver.continuity_generation
    changed = _context(
        frame=1,
        members=_candles(current_types, frame=10),
        source_key="source-b",
        session_key="session-b",
    )

    resolution = resolver.resolve_with_trace(frame_context=changed)

    assert resolution.result.status is CurrentCandleIdentityStatus.UNAVAILABLE
    assert resolution.trace.reset_reason is (
        CurrentCandleIdentityResetReason.SOURCE_CHANGED
    )
    assert resolution.result.terminal_region is None
    assert resolver.continuity_generation == generation + 1


def test_stop_and_start_create_fresh_generation_and_clear_tracking() -> None:
    resolver, current_types = _tracking_resolver()
    generation = resolver.continuity_generation

    resolver.stop_session()
    assert resolver.continuity_generation == generation + 1
    assert resolver.lifecycle is CurrentCandleIdentityLifecycle.BOOTSTRAPPING
    assert resolver.last_reset_reason is (
        CurrentCandleIdentityResetReason.SESSION_STOPPED
    )
    resolver.start_session(source_key="source-a", session_key="session-new")
    assert resolver.continuity_generation == generation + 2
    assert resolver.last_reset_reason is (
        CurrentCandleIdentityResetReason.SESSION_STARTED
    )

    first = _context(
        frame=1,
        members=_candles(current_types, frame=20),
        session_key="session-new",
    )
    result = resolver.resolve(frame_context=first)

    assert result.status is CurrentCandleIdentityStatus.UNAVAILABLE
    assert result.terminal_region is None


def test_membership_unavailable_never_falls_back_to_raw_final_candles() -> None:
    resolver, current_types = _tracking_resolver()
    raw = _candles(current_types, frame=4)
    frame = _context(
        frame=4,
        members=raw,
        membership_available=False,
    )

    resolution = resolver.resolve_with_trace(frame_context=frame)

    assert resolution.result.status is CurrentCandleIdentityStatus.UNAVAILABLE
    assert resolution.result.candidate_id is None
    assert resolution.trace.internal_state is CurrentCandleIdentityLifecycle.DEGRADED
    assert resolution.trace.reset_reason is (
        CurrentCandleIdentityResetReason.MEMBERSHIP_UNAVAILABLE
    )


def test_dropped_frame_degrades_or_resets_instead_of_assuming_rollover() -> None:
    resolver, current_types = _tracking_resolver()
    frame = _context(frame=5, members=_candles(current_types, frame=5))

    resolution = resolver.resolve_with_trace(frame_context=frame)

    assert resolution.result.status is CurrentCandleIdentityStatus.UNAVAILABLE
    assert resolution.trace.reset_reason is (
        CurrentCandleIdentityResetReason.ROLL_OVER_INCONSISTENT
    )


def test_double_slot_gap_is_not_reported_as_simple_missing_current() -> None:
    resolver, current_types = _tracking_resolver()
    frame = _context(frame=4, members=_candles(current_types[:-2], frame=4))

    resolution = resolver.resolve_with_trace(frame_context=frame)

    assert resolution.result.status is CurrentCandleIdentityStatus.AMBIGUOUS
    assert resolution.result.status is not CurrentCandleIdentityStatus.MISSING_FROM_VIEW
    assert resolution.trace.internal_state is CurrentCandleIdentityLifecycle.DEGRADED


def test_two_terminal_members_are_ambiguous() -> None:
    resolver, current_types = _tracking_resolver()
    members = _candles(current_types, frame=4)
    extra = replace(
        members[-1],
        candidate_id="frame4_competing_terminal",
        source_candidate_ids=("competing_source",),
        ordinal=len(members),
        x=members[-1].x + 2,
        is_latest=False,
    )
    frame = _context(frame=4, members=(*members, extra))

    resolution = resolver.resolve_with_trace(frame_context=frame)

    assert resolution.result.status is CurrentCandleIdentityStatus.AMBIGUOUS
    assert resolution.result.candidate_id is None


def test_expiry_overlay_to_right_does_not_become_shadow_current() -> None:
    resolver, current_types = _tracking_resolver()
    members = _candles(current_types[:-1], frame=4)
    terminal_template = _candles((current_types[-1],), frame=40)[0]
    overlay = replace(
        terminal_template,
        candidate_id="frame4_expiry_overlay",
        source_candidate_ids=("overlay_source",),
        ordinal=len(members),
        x=100 + len(current_types[:-1]) * 12,
        is_latest=False,
    )
    overlay_trace = CandleOverlayEvidenceTrace(
        evaluated_candidate_ids=(overlay.candidate_id,),
        evidence=(
            CandleOverlayEvidence(
                candidate_id=overlay.candidate_id,
                status=CandleOverlayEvidenceStatus.EXPIRY_OVERLAY,
                vertical_line_support_ratio=0.95,
                contact_gap_ratio=0.0,
                horizontal_alignment_ratio=0.05,
                cap_height_to_width_ratio=0.4,
                wickless=True,
                diagnostic="trusted_overlay_fixture",
            ),
        ),
    )
    frame = _context(
        frame=4,
        members=members,
        final_extras=(overlay,),
        overlay_evidence=overlay_trace,
    )

    result = resolver.resolve(frame_context=frame)

    assert result.status is CurrentCandleIdentityStatus.MISSING_FROM_VIEW
    assert result.candidate_id is None


def test_overlay_evidence_conflicting_with_terminal_member_is_ambiguous() -> None:
    resolver, current_types = _tracking_resolver()
    members = _candles(current_types, frame=4)
    terminal_id = members[-1].candidate_id
    overlay_trace = CandleOverlayEvidenceTrace(
        evaluated_candidate_ids=(terminal_id,),
        evidence=(
            CandleOverlayEvidence(
                candidate_id=terminal_id,
                status=CandleOverlayEvidenceStatus.EXPIRY_OVERLAY,
                vertical_line_support_ratio=0.95,
                contact_gap_ratio=0.0,
                horizontal_alignment_ratio=0.05,
                cap_height_to_width_ratio=0.4,
                wickless=True,
                diagnostic="conflicting_overlay_fixture",
            ),
        ),
    )
    frame = _context(
        frame=4,
        members=members,
        overlay_evidence=overlay_trace,
    )

    result = resolver.resolve(frame_context=frame)

    assert result.status is CurrentCandleIdentityStatus.AMBIGUOUS
    assert result.candidate_id is None


def test_bootstrap_and_tracking_do_not_require_expiry_evidence() -> None:
    resolver = CurrentCandleIdentityResolver()
    frames = _bootstrap_frames()

    result = None
    for frame in frames:
        assert frame.expiry_evidence_consistent is None
        result = resolver.resolve(frame_context=frame)

    assert result is not None
    assert result.status is CurrentCandleIdentityStatus.CONFIRMED


def test_expiry_disagreement_is_traced_without_overriding_tracking() -> None:
    resolver, current_types = _tracking_resolver()
    frame = _context(
        frame=4,
        members=_candles(current_types, frame=4),
        expiry_evidence_consistent=False,
    )

    resolution = resolver.resolve_with_trace(frame_context=frame)

    assert resolution.result.status is CurrentCandleIdentityStatus.CONFIRMED
    assert resolution.trace.expiry_evidence_consistent is False


def test_session03_f200_like_clipped_close_does_not_change_identity_core() -> None:
    resolver = CurrentCandleIdentityResolver()
    frames = _bootstrap_frames(clipped_third_terminal=True)

    result = None
    for frame in frames:
        result = resolver.resolve(frame_context=frame)

    assert result is not None
    assert result.status is CurrentCandleIdentityStatus.CONFIRMED
    assert frames[-1].member_candles[-1].observability is not None
    assert frames[-1].member_candles[-1].observability.body_touches_bottom is True


@pytest.mark.parametrize("oracle_name", ["session05_f11", "session05_f67"])
def test_session05_missing_current_oracles_report_missing_from_view(
    oracle_name: str,
) -> None:
    resolver, current_types = _tracking_resolver()
    frame = _context(frame=4, members=_candles(current_types[:-1], frame=4))

    result = resolver.resolve(frame_context=frame)

    assert oracle_name
    assert result.status is CurrentCandleIdentityStatus.MISSING_FROM_VIEW


class _ExplodingMatcher(CurrentCandleIdentityMatcher):
    def match(self, **kwargs: object):  # type: ignore[no-untyped-def]
        raise RuntimeError("simulated operational failure")


def test_unexpected_operational_error_fails_soft_without_partial_tracking() -> None:
    config = CurrentCandleIdentityConfig()
    resolver = CurrentCandleIdentityResolver(
        config=config,
        matcher=_ExplodingMatcher(config),
    )
    first, second, third = _bootstrap_frames()
    resolver.resolve(frame_context=first)
    generation = resolver.continuity_generation

    failed = resolver.resolve_with_trace(frame_context=second)

    assert failed.result.status is CurrentCandleIdentityStatus.UNAVAILABLE
    assert failed.trace.reset_reason is CurrentCandleIdentityResetReason.INTERNAL_ERROR
    assert resolver.continuity_generation == generation + 1
    assert resolver.lifecycle is CurrentCandleIdentityLifecycle.BOOTSTRAPPING
    assert resolver.resolve(frame_context=third).status is (
        CurrentCandleIdentityStatus.UNAVAILABLE
    )


def test_concurrent_duplicate_frame_commits_identity_at_most_once() -> None:
    resolver, current_types = _tracking_resolver()
    frame = _context(frame=4, members=_candles(current_types, frame=4))
    statuses: list[CurrentCandleIdentityStatus] = []

    def resolve_frame() -> None:
        statuses.append(resolver.resolve(frame_context=frame).status)

    threads = (Thread(target=resolve_frame), Thread(target=resolve_frame))
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert statuses.count(CurrentCandleIdentityStatus.CONFIRMED) == 1
    assert statuses.count(CurrentCandleIdentityStatus.UNAVAILABLE) == 1
