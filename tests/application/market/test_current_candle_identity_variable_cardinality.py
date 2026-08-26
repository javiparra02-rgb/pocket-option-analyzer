from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from pocket_option_analyzer.application.market import (
    CurrentCandleFrameContext,
    CurrentCandleIdentityLifecycle,
    CurrentCandleIdentityMatcher,
    CurrentCandleIdentityResolver,
    CurrentCandleIdentityStatus,
    CurrentCandleTranslationHypothesis,
    TemporalRolloverEvaluationStatus,
    TemporalRolloverRejectionReason,
    TerminalSeedEvaluationStatus,
    TrackingTerminalDecisionReason,
)
from pocket_option_analyzer.vision.models import (
    CandleColor,
    CandleGeometry,
    CandleObservability,
    CandleOverlayEvidence,
    CandleOverlayEvidenceStatus,
    CandleOverlayEvidenceTrace,
    CandleSeriesMembershipRunTrace,
    CandleSeriesMembershipStatus,
    CandleSeriesMembershipTrace,
    CandleType,
    FinalCandleTrace,
)

_START = datetime(2026, 8, 26, tzinfo=UTC)
_PITCH = 12
_DEFAULT_WIDTH = 8


def _types(count: int) -> tuple[CandleType, ...]:
    return tuple(
        CandleType.BULLISH if index % 2 == 0 else CandleType.BEARISH
        for index in range(count)
    )


def _candles(
    candle_types: tuple[CandleType, ...],
    *,
    frame: int,
    start_x: int,
    terminal_close_clipped: bool = False,
    terminal_width: int = _DEFAULT_WIDTH,
) -> tuple[FinalCandleTrace, ...]:
    candles: list[FinalCandleTrace] = []
    for index, original_type in enumerate(candle_types):
        terminal = index == len(candle_types) - 1
        candle_type = original_type
        body_top_y = 20 + index
        body_bottom_y = body_top_y + 8
        if terminal and terminal_close_clipped:
            candle_type = CandleType.BEARISH
            body_bottom_y = 99
        width = terminal_width if terminal else _DEFAULT_WIDTH
        x = start_x + index * _PITCH - (width - _DEFAULT_WIDTH) // 2
        candles.append(
            FinalCandleTrace(
                candidate_id=f"frame{frame}_candidate{index}",
                source_candidate_ids=(f"source{frame}_{index}",),
                ordinal=index,
                x=x,
                y=body_top_y - 3,
                width=width,
                height=body_bottom_y - body_top_y + 7,
                area=width * (body_bottom_y - body_top_y + 7),
                color=(
                    CandleColor.WHITE
                    if candle_type is CandleType.BULLISH
                    else CandleColor.RED
                ),
                candle_type=candle_type,
                geometry=CandleGeometry(
                    high_y=body_top_y - 3,
                    body_top_y=body_top_y,
                    body_bottom_y=body_bottom_y,
                    low_y=body_bottom_y + 3 if body_bottom_y < 99 else 99,
                ),
                observability=CandleObservability(
                    roi_height=100,
                    body_top_y=body_top_y,
                    body_bottom_y=body_bottom_y,
                    body_touches_top=False,
                    body_touches_bottom=body_bottom_y == 99,
                ),
                is_latest=terminal,
            )
        )
    return tuple(candles)


def _context(
    *,
    frame: int,
    members: tuple[FinalCandleTrace, ...],
    pitch: float = float(_PITCH),
    roi_width: int = 300,
    source_key: str = "source-a",
    session_key: str = "session-a",
    overlay_evidence: CandleOverlayEvidenceTrace | None = None,
) -> CurrentCandleFrameContext:
    member_ids = tuple(candle.candidate_id for candle in members)
    membership = CandleSeriesMembershipTrace(
        status=CandleSeriesMembershipStatus.AVAILABLE,
        evaluated_candidate_ids=member_ids,
        member_candidate_ids=member_ids,
        excluded_candidates=(),
        evaluated_gaps=(),
        estimated_pitch_px=pitch,
        candidate_runs=(
            CandleSeriesMembershipRunTrace(
                run_id="selected",
                candidate_ids=member_ids,
                selected=True,
            ),
        ),
        selected_run_support=len(member_ids),
        latest_candidate_id=member_ids[-1],
        diagnostic="variable_cardinality_fixture",
    )
    return CurrentCandleFrameContext(
        frame_id=frame,
        wall_timestamp=_START + timedelta(seconds=frame),
        monotonic_timestamp=float(frame),
        roi_width=roi_width,
        roi_height=100,
        source_key=source_key,
        session_key=session_key,
        membership=membership,
        final_candles=members,
        overlay_evidence=overlay_evidence,
    )


def _expiry_overlay_trace(candidate_id: str) -> CandleOverlayEvidenceTrace:
    return CandleOverlayEvidenceTrace(
        evaluated_candidate_ids=(candidate_id,),
        evidence=(
            CandleOverlayEvidence(
                candidate_id=candidate_id,
                status=CandleOverlayEvidenceStatus.EXPIRY_OVERLAY,
                vertical_line_support_ratio=0.95,
                contact_gap_ratio=0.0,
                horizontal_alignment_ratio=0.05,
                cap_height_to_width_ratio=0.4,
                wickless=True,
                diagnostic="variable_cardinality_expiry_overlay_fixture",
            ),
        ),
    )


def _observed_bootstrap(
    *,
    terminal_width: int = _DEFAULT_WIDTH,
) -> tuple[
    CurrentCandleIdentityResolver,
    tuple[CandleType, ...],
    CurrentCandleFrameContext,
]:
    resolver = CurrentCandleIdentityResolver()
    first_types = _types(7)
    rollover_types = (*first_types, CandleType.BEARISH)
    first = _context(
        frame=12,
        members=_candles(first_types, frame=12, start_x=100),
    )
    rollover = _context(
        frame=13,
        members=_candles(
            rollover_types,
            frame=13,
            start_x=88,
            terminal_width=terminal_width,
        ),
    )
    stable = _context(
        frame=14,
        members=_candles(
            rollover_types,
            frame=14,
            start_x=88,
            terminal_width=terminal_width,
        ),
    )
    resolver.resolve(frame_context=first)
    pending = resolver.resolve_with_trace(frame_context=rollover)
    confirmed = resolver.resolve_with_trace(frame_context=stable)
    assert pending.trace.trusted_rollover_evaluation.status is (
        TemporalRolloverEvaluationStatus.ACCEPTED
    )
    assert pending.trace.terminal_seed_evaluation.status is (
        TerminalSeedEvaluationStatus.OBSERVED
    )
    assert confirmed.result.status is CurrentCandleIdentityStatus.CONFIRMED
    assert confirmed.trace.internal_state is CurrentCandleIdentityLifecycle.TRACKING
    assert confirmed.trace.tracking_terminal_evaluation.region_moved is False
    return resolver, rollover_types, stable


def test_variable_7_to_8_rollover_bootstraps_after_stable_confirmation() -> None:
    resolver, _, stable = _observed_bootstrap()

    assert resolver.last_trace is not None
    assert resolver.last_trace.bootstrap_confirmation_evaluation.accepted is True
    assert resolver.last_trace.chosen_candidate_id == (
        stable.member_candles[-1].candidate_id
    )
    assert resolver.last_trace.terminal_region is not None
    assert resolver.last_trace.terminal_region.learned_from_frame_ids == (12, 13, 14)


def test_cold_bootstrap_8_to_7_terminal_absent_stays_unavailable() -> None:
    resolver = CurrentCandleIdentityResolver()
    first_types = _types(8)
    first = _context(
        frame=1,
        members=_candles(first_types, frame=1, start_x=88),
    )
    absent = _context(
        frame=2,
        members=_candles(first_types[1:], frame=2, start_x=88),
    )

    resolver.resolve(frame_context=first)
    resolution = resolver.resolve_with_trace(frame_context=absent)

    assert resolution.result.status is CurrentCandleIdentityStatus.UNAVAILABLE
    assert resolution.result.terminal_region is None
    assert resolution.trace.internal_state is (
        CurrentCandleIdentityLifecycle.BOOTSTRAPPING
    )
    assert resolution.trace.trusted_rollover_evaluation.status is (
        TemporalRolloverEvaluationStatus.ACCEPTED
    )
    assert resolution.trace.terminal_seed_evaluation.status is (
        TerminalSeedEvaluationStatus.ABSENT
    )
    assert resolution.trace.bootstrap_confirmation_evaluation.pending_after is False


def test_multiple_terminal_absent_rollovers_never_create_cold_identity() -> None:
    resolver = CurrentCandleIdentityResolver()
    eight_types = _types(8)
    frames = (
        _context(
            frame=1,
            members=_candles(eight_types, frame=1, start_x=88),
        ),
        _context(
            frame=2,
            members=_candles(eight_types[1:], frame=2, start_x=88),
        ),
        _context(
            frame=3,
            members=_candles(eight_types[2:], frame=3, start_x=88),
        ),
    )

    results = tuple(
        resolver.resolve_with_trace(frame_context=frame) for frame in frames
    )

    assert all(result.result.candidate_id is None for result in results)
    assert all(result.result.terminal_region is None for result in results)
    assert results[-1].trace.terminal_seed_evaluation.status is (
        TerminalSeedEvaluationStatus.ABSENT
    )


def test_future_observed_rollover_can_bootstrap_after_absent_rollovers() -> None:
    resolver = CurrentCandleIdentityResolver()
    eight_types = _types(8)
    seven_types = eight_types[1:]
    six_types = seven_types[1:]
    contexts = (
        _context(
            frame=1,
            members=_candles(eight_types, frame=1, start_x=88),
        ),
        _context(
            frame=2,
            members=_candles(seven_types, frame=2, start_x=88),
        ),
        _context(
            frame=3,
            members=_candles(six_types, frame=3, start_x=88),
        ),
    )
    for context in contexts:
        resolver.resolve(frame_context=context)
    observed_types = (*six_types, CandleType.BULLISH)
    observed = _context(
        frame=4,
        members=_candles(observed_types, frame=4, start_x=76),
    )
    stable = _context(
        frame=5,
        members=_candles(observed_types, frame=5, start_x=76),
    )

    pending = resolver.resolve_with_trace(frame_context=observed)
    confirmed = resolver.resolve_with_trace(frame_context=stable)

    assert pending.trace.terminal_seed_evaluation.status is (
        TerminalSeedEvaluationStatus.OBSERVED
    )
    assert confirmed.result.status is CurrentCandleIdentityStatus.CONFIRMED


def test_bootstrap_rejects_expiry_overlay_as_observed_terminal_seed() -> None:
    resolver = CurrentCandleIdentityResolver()
    first_types = _types(7)
    rollover_types = (*first_types, CandleType.BEARISH)
    first = _context(
        frame=12,
        members=_candles(first_types, frame=12, start_x=100),
    )
    rollover_members = _candles(
        rollover_types,
        frame=13,
        start_x=88,
    )
    rollover = _context(
        frame=13,
        members=rollover_members,
        overlay_evidence=_expiry_overlay_trace(
            rollover_members[-1].candidate_id
        ),
    )

    resolver.resolve(frame_context=first)
    resolution = resolver.resolve_with_trace(frame_context=rollover)

    assert resolution.trace.trusted_rollover_evaluation.status is (
        TemporalRolloverEvaluationStatus.ACCEPTED
    )
    assert resolution.trace.terminal_seed_evaluation.status is (
        TerminalSeedEvaluationStatus.OVERLAY
    )
    assert resolution.result.status is CurrentCandleIdentityStatus.AMBIGUOUS
    assert resolution.trace.internal_state is (
        CurrentCandleIdentityLifecycle.BOOTSTRAPPING
    )
    assert resolution.trace.terminal_region is None
    assert resolution.trace.bootstrap_confirmation_evaluation.pending_after is False


def test_tracking_observed_rollover_confirms_only_unmatched_current() -> None:
    resolver, current_types, _ = _observed_bootstrap()
    rollover_types = (*current_types[1:], CandleType.BULLISH)
    rollover = _context(
        frame=15,
        members=_candles(rollover_types, frame=15, start_x=88),
    )

    resolution = resolver.resolve_with_trace(frame_context=rollover)

    expected = rollover.member_candles[-1].candidate_id
    assert resolution.result.status is CurrentCandleIdentityStatus.CONFIRMED
    assert resolution.result.candidate_id == expected
    assert resolution.trace.terminal_seed_evaluation.candidate_id == expected
    assert resolution.trace.tracking_terminal_evaluation.region_after is (
        resolution.result.terminal_region
    )


def test_f68_f69_like_absence_preserves_region_without_false_current() -> None:
    resolver, current_types, _ = _observed_bootstrap()
    region = resolver.last_trace.terminal_region if resolver.last_trace else None
    assert region is not None
    absent_types = current_types[1:]
    rollover = _context(
        frame=15,
        members=_candles(
            absent_types,
            frame=15,
            start_x=88,
            terminal_close_clipped=True,
        ),
    )
    stable = _context(
        frame=16,
        members=_candles(
            tuple(candle.candle_type for candle in rollover.member_candles),
            frame=16,
            start_x=88,
            terminal_close_clipped=True,
        ),
    )

    f68 = resolver.resolve_with_trace(frame_context=rollover)
    f69 = resolver.resolve_with_trace(frame_context=stable)

    assert f68.result.status is CurrentCandleIdentityStatus.AMBIGUOUS
    assert f68.result.candidate_id is None
    assert f68.trace.terminal_seed_evaluation.status is (
        TerminalSeedEvaluationStatus.ABSENT
    )
    assert f68.trace.tracking_terminal_evaluation.region_before == region
    assert f68.trace.tracking_terminal_evaluation.region_after == region
    assert f68.trace.missing_evidence is not None
    assert f68.trace.missing_evidence.previous_slot_fully_observable is False
    assert f69.result.status is CurrentCandleIdentityStatus.AMBIGUOUS
    assert f69.result.terminal_region == region
    assert resolver.lifecycle is CurrentCandleIdentityLifecycle.DEGRADED


def test_f96_f97_like_accumulated_gap_never_projects_false_identity() -> None:
    resolver, current_types, _ = _observed_bootstrap()
    region = resolver.last_trace.terminal_region if resolver.last_trace else None
    assert region is not None
    seven_types = current_types[1:]
    f68 = _context(
        frame=15,
        members=_candles(
            seven_types,
            frame=15,
            start_x=88,
            terminal_close_clipped=True,
        ),
    )
    f69 = _context(
        frame=16,
        members=_candles(
            tuple(candle.candle_type for candle in f68.member_candles),
            frame=16,
            start_x=88,
            terminal_close_clipped=True,
        ),
    )
    resolver.resolve(frame_context=f68)
    resolver.resolve(frame_context=f69)
    six_types = tuple(candle.candle_type for candle in f69.member_candles[1:])
    f96 = _context(
        frame=17,
        members=_candles(
            six_types,
            frame=17,
            start_x=88,
            terminal_close_clipped=True,
        ),
    )
    f97 = _context(
        frame=18,
        members=_candles(
            tuple(candle.candle_type for candle in f96.member_candles),
            frame=18,
            start_x=88,
            terminal_close_clipped=True,
        ),
    )

    first = resolver.resolve_with_trace(frame_context=f96)
    second = resolver.resolve_with_trace(frame_context=f97)

    assert first.result.status is CurrentCandleIdentityStatus.AMBIGUOUS
    assert second.result.status is CurrentCandleIdentityStatus.AMBIGUOUS
    assert first.result.terminal_region == region
    assert second.result.terminal_region == region
    assert first.trace.missing_evidence is not None
    assert first.trace.missing_evidence.previous_slot_candidate_id is None
    assert first.trace.tracking_terminal_evaluation.region_moved is False


def test_historical_member_inside_wide_region_is_not_promoted_on_rollover() -> None:
    resolver, current_types, _ = _observed_bootstrap()
    wider = _context(
        frame=15,
        members=_candles(
            current_types,
            frame=15,
            start_x=88,
            terminal_width=24,
        ),
    )
    assert resolver.resolve(frame_context=wider).status is (
        CurrentCandleIdentityStatus.CONFIRMED
    )
    region = resolver.last_trace.terminal_region if resolver.last_trace else None
    assert region is not None
    absent = _context(
        frame=16,
        members=_candles(current_types[1:], frame=16, start_x=88),
    )
    assert region.contains(
        absent.member_candles[-1].x + absent.member_candles[-1].width / 2
    )

    resolution = resolver.resolve_with_trace(frame_context=absent)

    assert resolution.result.status is CurrentCandleIdentityStatus.AMBIGUOUS
    assert resolution.result.candidate_id is None
    assert resolution.result.terminal_region == region
    assert resolution.trace.terminal_seed_evaluation.status is (
        TerminalSeedEvaluationStatus.ABSENT
    )


def test_f40_f41_like_unavailable_matches_preserve_region_and_f42_recovers() -> None:
    resolver, current_types, _ = _observed_bootstrap()
    region = resolver.last_trace.terminal_region if resolver.last_trace else None
    assert region is not None
    frames = (
        _context(
            frame=15,
            members=_candles(
                (CandleType.DOJI,) * len(current_types),
                frame=15,
                start_x=88,
            ),
        ),
        _context(
            frame=16,
            members=_candles(
                current_types,
                frame=16,
                start_x=88,
            ),
        ),
        _context(
            frame=17,
            members=_candles(
                current_types,
                frame=17,
                start_x=88,
            ),
        ),
    )

    first = resolver.resolve_with_trace(frame_context=frames[0])
    second = resolver.resolve_with_trace(frame_context=frames[1])
    recovered = resolver.resolve_with_trace(frame_context=frames[2])

    assert first.result.status is CurrentCandleIdentityStatus.UNAVAILABLE
    assert second.result.status is CurrentCandleIdentityStatus.UNAVAILABLE
    assert first.result.terminal_region == region
    assert second.result.terminal_region == region
    assert recovered.result.status is CurrentCandleIdentityStatus.CONFIRMED
    assert recovered.trace.internal_state is CurrentCandleIdentityLifecycle.TRACKING
    assert recovered.trace.tracking_terminal_evaluation.decision_reason is (
        TrackingTerminalDecisionReason.REGION_UPDATED_FROM_STABLE
    )


@pytest.mark.parametrize(
    ("unmatched_previous_indexes", "unmatched_current_indexes", "reason"),
    [
        ((), (), TemporalRolloverRejectionReason.NO_BOUNDARY_CHANGE),
        (
            (2,),
            (-1,),
            TemporalRolloverRejectionReason.PREVIOUS_BOUNDARY_INCOMPATIBLE,
        ),
        (
            (0, 1),
            (-1,),
            TemporalRolloverRejectionReason.PREVIOUS_BOUNDARY_INCOMPATIBLE,
        ),
        (
            (0,),
            (2,),
            TemporalRolloverRejectionReason.CURRENT_BOUNDARY_INCOMPATIBLE,
        ),
        (
            (0,),
            (-2, -1),
            TemporalRolloverRejectionReason.CURRENT_BOUNDARY_INCOMPATIBLE,
        ),
    ],
)
def test_interior_multiple_or_empty_boundary_sets_are_rejected(
    unmatched_previous_indexes: tuple[int, ...],
    unmatched_current_indexes: tuple[int, ...],
    reason: TemporalRolloverRejectionReason,
) -> None:
    previous = _context(
        frame=1,
        members=_candles(_types(7), frame=1, start_x=100),
    )
    current_types = (*_types(7), CandleType.BEARISH)
    current = _context(
        frame=2,
        members=_candles(current_types, frame=2, start_x=88),
    )
    matcher = CurrentCandleIdentityMatcher()
    match = matcher.match(
        previous=previous.member_candles,
        current=current.member_candles,
        estimated_pitch_px=float(_PITCH),
    )
    rollover = replace(
        match.rollover,
        unmatched_previous_candidate_ids=tuple(
            previous.member_candles[index].candidate_id
            for index in unmatched_previous_indexes
        ),
        unmatched_current_candidate_ids=tuple(
            current.member_candles[index].candidate_id
            for index in unmatched_current_indexes
        ),
    )
    altered = replace(
        match,
        status=match.status,
        selected_hypothesis=CurrentCandleTranslationHypothesis.ROLLOVER,
        rollover=rollover,
    )

    evaluation = CurrentCandleIdentityResolver()._evaluate_temporal_rollover(
        previous,
        current,
        altered,
    )

    assert evaluation.status is TemporalRolloverEvaluationStatus.REJECTED
    assert evaluation.rejection_reason is reason


def test_candidate_ids_are_frame_local_not_temporal_identity() -> None:
    _, _, stable = _observed_bootstrap()
    first = _context(
        frame=12,
        members=_candles(_types(7), frame=12, start_x=100),
    )

    assert set(first.membership.member_candidate_ids).isdisjoint(
        stable.membership.member_candidate_ids
    )
