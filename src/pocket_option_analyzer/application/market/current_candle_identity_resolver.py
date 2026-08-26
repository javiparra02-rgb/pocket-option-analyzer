from __future__ import annotations

from dataclasses import dataclass, replace
from math import isclose
from threading import RLock

from pocket_option_analyzer.vision.models.candle_detection_trace import (
    FinalCandleTrace,
)
from pocket_option_analyzer.vision.models.candle_overlay_evidence import (
    CandleOverlayEvidenceStatus,
)
from pocket_option_analyzer.vision.models.candle_series_membership import (
    CandleSeriesMembershipStatus,
)

from .current_candle_identity import (
    BootstrapConfirmationEvaluation,
    BootstrapConfirmationRejectionReason,
    CurrentCandleFrameContext,
    CurrentCandleIdentityConfig,
    CurrentCandleIdentityEvidence,
    CurrentCandleIdentityLifecycle,
    CurrentCandleIdentityResetReason,
    CurrentCandleIdentityResolution,
    CurrentCandleIdentityResult,
    CurrentCandleIdentitySource,
    CurrentCandleIdentityStatus,
    CurrentCandleIdentityTrace,
    CurrentCandleMatchStatus,
    CurrentCandleMissingEvidence,
    CurrentCandleSequenceMatch,
    CurrentCandleTranslationHypothesis,
    TemporalRolloverEvaluationStatus,
    TemporalRolloverRejectionReason,
    TerminalSeedEvaluation,
    TerminalSeedEvaluationStatus,
    TerminalSeedProvenance,
    TerminalSlotRegion,
    TrackingTerminalDecisionReason,
    TrackingTerminalEvaluation,
    TrustedRolloverEvaluation,
    candle_center_x,
    pitches_are_compatible,
)
from .current_candle_identity_matcher import CurrentCandleIdentityMatcher


@dataclass(frozen=True, slots=True)
class _PendingBootstrap:
    terminal_region: TerminalSlotRegion
    rollover_match: CurrentCandleSequenceMatch


@dataclass(frozen=True, slots=True)
class _ResolverState:
    lifecycle: CurrentCandleIdentityLifecycle
    continuity_generation: int
    active: bool
    source_key: str | None = None
    session_key: str | None = None
    previous_context: CurrentCandleFrameContext | None = None
    terminal_region: TerminalSlotRegion | None = None
    pending_bootstrap: _PendingBootstrap | None = None
    last_trace: CurrentCandleIdentityTrace | None = None
    last_reset_reason: CurrentCandleIdentityResetReason | None = None


@dataclass(frozen=True, slots=True)
class _ResolutionTelemetry:
    trusted_rollover: TrustedRolloverEvaluation
    terminal_seed: TerminalSeedEvaluation
    bootstrap_confirmation: BootstrapConfirmationEvaluation
    tracking_terminal: TrackingTerminalEvaluation

    @classmethod
    def empty(cls) -> _ResolutionTelemetry:
        return cls(
            trusted_rollover=TrustedRolloverEvaluation.not_evaluated(),
            terminal_seed=TerminalSeedEvaluation.not_evaluated(),
            bootstrap_confirmation=BootstrapConfirmationEvaluation.not_evaluated(),
            tracking_terminal=TrackingTerminalEvaluation.not_evaluated(),
        )


class CurrentCandleIdentityResolver:
    """Thread-safe stateful shadow resolver for continuous candle identity.

    The core has no runtime wiring or persistence. State updates are assembled as
    immutable snapshots and published only after one frame resolves successfully.
    """

    def __init__(
        self,
        *,
        config: CurrentCandleIdentityConfig | None = None,
        matcher: CurrentCandleIdentityMatcher | None = None,
    ) -> None:
        effective_config = (
            config
            or (matcher.config if matcher is not None else None)
            or CurrentCandleIdentityConfig()
        )
        if matcher is not None and matcher.config != effective_config:
            raise ValueError("Matcher y resolver deben compartir configuración.")
        self._config = effective_config
        self._matcher = matcher or CurrentCandleIdentityMatcher(effective_config)
        self._lock = RLock()
        self._state = _ResolverState(
            lifecycle=CurrentCandleIdentityLifecycle.BOOTSTRAPPING,
            continuity_generation=0,
            active=False,
        )

    @property
    def config(self) -> CurrentCandleIdentityConfig:
        """Return the immutable provisional configuration."""

        return self._config

    @property
    def lifecycle(self) -> CurrentCandleIdentityLifecycle:
        """Return a lock-protected lifecycle snapshot."""

        with self._lock:
            return self._state.lifecycle

    @property
    def continuity_generation(self) -> int:
        """Return the current reset generation."""

        with self._lock:
            return self._state.continuity_generation

    @property
    def last_trace(self) -> CurrentCandleIdentityTrace | None:
        """Return the last committed immutable trace, if any."""

        with self._lock:
            return self._state.last_trace

    @property
    def last_reset_reason(self) -> CurrentCandleIdentityResetReason | None:
        """Return the reason attached to the current reset generation."""

        with self._lock:
            return self._state.last_reset_reason

    def start_session(self, *, source_key: str, session_key: str) -> None:
        """Start a fresh identity generation for an opaque source/session pair."""

        if not source_key or not session_key:
            raise ValueError("source_key y session_key no pueden estar vacíos.")
        with self._lock:
            self._state = self._fresh_state(
                generation=self._state.continuity_generation + 1,
                active=True,
                source_key=source_key,
                session_key=session_key,
                reset_reason=CurrentCandleIdentityResetReason.SESSION_STARTED,
            )

    def stop_session(self) -> None:
        """Clear trusted history so identity cannot cross a stopped session."""

        with self._lock:
            self._state = self._fresh_state(
                generation=self._state.continuity_generation + 1,
                active=False,
                reset_reason=CurrentCandleIdentityResetReason.SESSION_STOPPED,
            )

    def reset(
        self,
        reason: CurrentCandleIdentityResetReason = (
            CurrentCandleIdentityResetReason.EXPLICIT_RESET
        ),
    ) -> None:
        """Explicitly clear temporal identity while retaining active ownership."""

        if reason in (
            CurrentCandleIdentityResetReason.SESSION_STARTED,
            CurrentCandleIdentityResetReason.SESSION_STOPPED,
        ):
            raise ValueError("Use start_session() o stop_session() para esa razón.")
        with self._lock:
            state = self._state
            self._state = self._fresh_state(
                generation=state.continuity_generation + 1,
                active=state.active,
                source_key=state.source_key,
                session_key=state.session_key,
                reset_reason=reason,
            )

    def resolve(
        self,
        *,
        frame_context: CurrentCandleFrameContext,
    ) -> CurrentCandleIdentityResult:
        """Resolve one frame and return only the small semantic result."""

        return self.resolve_with_trace(frame_context=frame_context).result

    def resolve_with_trace(
        self,
        *,
        frame_context: CurrentCandleFrameContext,
    ) -> CurrentCandleIdentityResolution:
        """Resolve one frame atomically and return result plus diagnostics."""

        with self._lock:
            original_state = self._state
            try:
                next_state, resolution = self._resolve_transaction(
                    original_state,
                    frame_context,
                )
            except (AssertionError, TypeError, ValueError):
                raise
            except Exception as error:  # pragma: no cover - defensive boundary
                next_state, resolution = self._fail_soft(
                    original_state,
                    frame_context,
                    error,
                )
            if resolution.trace.reset_reason in (
                CurrentCandleIdentityResetReason.FRAME_OUT_OF_ORDER,
                CurrentCandleIdentityResetReason.TIME_REGRESSION,
            ):
                return resolution
            self._state = replace(next_state, last_trace=resolution.trace)
            return resolution

    def _resolve_transaction(
        self,
        state: _ResolverState,
        context: CurrentCandleFrameContext,
    ) -> tuple[_ResolverState, CurrentCandleIdentityResolution]:
        if not state.active:
            state = self._fresh_state(
                generation=state.continuity_generation + 1,
                active=True,
                source_key=context.source_key,
                session_key=context.session_key,
                reset_reason=CurrentCandleIdentityResetReason.SESSION_STARTED,
            )
        elif (
            state.source_key != context.source_key
            or state.session_key != context.session_key
        ):
            state = self._fresh_state(
                generation=state.continuity_generation + 1,
                active=True,
                source_key=context.source_key,
                session_key=context.session_key,
                reset_reason=CurrentCandleIdentityResetReason.SOURCE_CHANGED,
            )
            return self._seed_bootstrap(
                state,
                context,
                reset_reason=CurrentCandleIdentityResetReason.SOURCE_CHANGED,
            )

        ordering_reason = self._ordering_problem(state.previous_context, context)
        if ordering_reason is not None:
            return state, self._unavailable_resolution(
                context=context,
                state=state,
                diagnostic=ordering_reason.value,
                reset_reason=ordering_reason,
            )

        if not self._membership_available(context):
            degraded = replace(
                state,
                lifecycle=CurrentCandleIdentityLifecycle.DEGRADED,
                previous_context=None,
                pending_bootstrap=None,
                terminal_region=None,
                last_reset_reason=(
                    CurrentCandleIdentityResetReason.MEMBERSHIP_UNAVAILABLE
                ),
            )
            return degraded, self._unavailable_resolution(
                context=context,
                state=degraded,
                diagnostic="membership_unavailable_no_raw_fallback",
                reset_reason=CurrentCandleIdentityResetReason.MEMBERSHIP_UNAVAILABLE,
            )

        previous = state.previous_context
        if previous is None:
            return self._seed_bootstrap(state, context)

        discontinuity = self._continuity_problem(previous, context)
        if discontinuity is not None:
            reset_state = self._fresh_state(
                generation=state.continuity_generation + 1,
                active=True,
                source_key=context.source_key,
                session_key=context.session_key,
                reset_reason=discontinuity,
            )
            return self._seed_bootstrap(
                reset_state,
                context,
                reset_reason=discontinuity,
            )

        if (
            state.lifecycle is CurrentCandleIdentityLifecycle.DEGRADED
            and state.terminal_region is None
        ):
            reset_state = self._fresh_state(
                generation=state.continuity_generation + 1,
                active=True,
                source_key=context.source_key,
                session_key=context.session_key,
                reset_reason=CurrentCandleIdentityResetReason.EXPLICIT_RESET,
            )
            return self._seed_bootstrap(
                reset_state,
                context,
                reset_reason=CurrentCandleIdentityResetReason.EXPLICIT_RESET,
            )

        pitch = context.estimated_pitch_px
        assert pitch is not None
        sequence_match = self._matcher.match(
            previous=previous.member_candles,
            current=context.member_candles,
            estimated_pitch_px=pitch,
        )
        if state.lifecycle is CurrentCandleIdentityLifecycle.BOOTSTRAPPING:
            return self._resolve_bootstrap(state, context, sequence_match)
        return self._resolve_tracking(state, context, sequence_match)

    def _resolve_bootstrap(
        self,
        state: _ResolverState,
        context: CurrentCandleFrameContext,
        sequence_match: CurrentCandleSequenceMatch,
    ) -> tuple[_ResolverState, CurrentCandleIdentityResolution]:
        pending = state.pending_bootstrap
        if pending is None:
            trusted_rollover = self._evaluate_temporal_rollover(
                state.previous_context,
                context,
                sequence_match,
            )
            if trusted_rollover.temporal_rollover_trusted:
                assert state.previous_context is not None
                terminal_seed = self._evaluate_terminal_seed(
                    context=context,
                    trusted_rollover=trusted_rollover,
                )
                if terminal_seed.status is not TerminalSeedEvaluationStatus.OBSERVED:
                    next_state = replace(
                        state,
                        previous_context=context,
                        terminal_region=None,
                        pending_bootstrap=None,
                    )
                    is_absent = (
                        terminal_seed.status is TerminalSeedEvaluationStatus.ABSENT
                    )
                    status = (
                        CurrentCandleIdentityStatus.UNAVAILABLE
                        if is_absent
                        else CurrentCandleIdentityStatus.AMBIGUOUS
                    )
                    telemetry = _ResolutionTelemetry(
                        trusted_rollover=trusted_rollover,
                        terminal_seed=terminal_seed,
                        bootstrap_confirmation=(
                            BootstrapConfirmationEvaluation(
                                evaluated=False,
                                accepted=False,
                                rejection_reason=(
                                    BootstrapConfirmationRejectionReason.TERMINAL_SEED_ABSENT
                                    if is_absent
                                    else (
                                        BootstrapConfirmationRejectionReason.TERMINAL_SEED_INVALID
                                    )
                                ),
                                pending_before=False,
                                pending_after=False,
                                lifecycle_before=state.lifecycle,
                                lifecycle_after=next_state.lifecycle,
                                selected_stable=None,
                                provisional_region=None,
                                candidates_in_region=(),
                                candidate_count=0,
                                overlay_conflict=(
                                    terminal_seed.status
                                    is TerminalSeedEvaluationStatus.OVERLAY
                                ),
                                resulting_status=status,
                            )
                        ),
                        tracking_terminal=(
                            TrackingTerminalEvaluation.not_evaluated()
                        ),
                    )
                    diagnostic = (
                        "trusted_rollover_terminal_absent_bootstrap_waiting"
                        if is_absent
                        else "trusted_rollover_terminal_seed_not_usable"
                    )
                    return next_state, self._nonconclusive_resolution(
                        status=status,
                        context=context,
                        state=next_state,
                        diagnostic=diagnostic,
                        sequence_match=sequence_match,
                        rollover_suspected=True,
                        telemetry=telemetry,
                    )
                assert terminal_seed.candidate_id is not None
                terminal = self._member_by_id(context, terminal_seed.candidate_id)
                region = self._learn_terminal_region(
                    candidate=terminal,
                    context=context,
                    generation=state.continuity_generation,
                    frame_ids=(state.previous_context.frame_id, context.frame_id),
                )
                next_state = replace(
                    state,
                    previous_context=context,
                    pending_bootstrap=_PendingBootstrap(
                        terminal_region=region,
                        rollover_match=sequence_match,
                    ),
                )
                telemetry = _ResolutionTelemetry(
                    trusted_rollover=trusted_rollover,
                    terminal_seed=terminal_seed,
                    bootstrap_confirmation=BootstrapConfirmationEvaluation(
                        evaluated=False,
                        accepted=False,
                        rejection_reason=(
                            BootstrapConfirmationRejectionReason.NOT_EVALUATED
                        ),
                        pending_before=False,
                        pending_after=True,
                        lifecycle_before=state.lifecycle,
                        lifecycle_after=next_state.lifecycle,
                        selected_stable=None,
                        provisional_region=region,
                        candidates_in_region=(terminal.candidate_id,),
                        candidate_count=1,
                        overlay_conflict=False,
                        resulting_status=CurrentCandleIdentityStatus.UNAVAILABLE,
                    ),
                    tracking_terminal=TrackingTerminalEvaluation.not_evaluated(),
                )
                return next_state, self._unavailable_resolution(
                    context=context,
                    state=next_state,
                    diagnostic="trusted_rollover_pending_stable_confirmation",
                    sequence_match=sequence_match,
                    terminal_region=region,
                    rollover_suspected=True,
                    telemetry=telemetry,
                )
            next_state = replace(state, previous_context=context)
            status = (
                CurrentCandleIdentityStatus.AMBIGUOUS
                if sequence_match.status is CurrentCandleMatchStatus.AMBIGUOUS
                else CurrentCandleIdentityStatus.UNAVAILABLE
            )
            telemetry = _ResolutionTelemetry(
                trusted_rollover=trusted_rollover,
                terminal_seed=TerminalSeedEvaluation.not_evaluated(),
                bootstrap_confirmation=BootstrapConfirmationEvaluation(
                    evaluated=False,
                    accepted=False,
                    rejection_reason=(
                        BootstrapConfirmationRejectionReason.TEMPORAL_ROLLOVER_REJECTED
                    ),
                    pending_before=False,
                    pending_after=False,
                    lifecycle_before=state.lifecycle,
                    lifecycle_after=next_state.lifecycle,
                    selected_stable=None,
                    provisional_region=None,
                    candidates_in_region=(),
                    candidate_count=0,
                    overlay_conflict=False,
                    resulting_status=status,
                ),
                tracking_terminal=TrackingTerminalEvaluation.not_evaluated(),
            )
            return next_state, self._nonconclusive_resolution(
                status=status,
                context=context,
                state=next_state,
                diagnostic="bootstrap_waiting_for_trusted_rollover",
                sequence_match=sequence_match,
                rollover_suspected=(
                    sequence_match.selected_hypothesis
                    is CurrentCandleTranslationHypothesis.ROLLOVER
                ),
                telemetry=telemetry,
            )

        if (
            sequence_match.status is not CurrentCandleMatchStatus.SELECTED
            or sequence_match.selected_hypothesis
            is not CurrentCandleTranslationHypothesis.STABLE
        ):
            reset_state = self._fresh_state(
                generation=state.continuity_generation + 1,
                active=True,
                source_key=context.source_key,
                session_key=context.session_key,
                reset_reason=(
                    CurrentCandleIdentityResetReason.ROLL_OVER_INCONSISTENT
                ),
            )
            telemetry = _ResolutionTelemetry(
                trusted_rollover=TrustedRolloverEvaluation.not_evaluated(),
                terminal_seed=TerminalSeedEvaluation.not_evaluated(),
                bootstrap_confirmation=BootstrapConfirmationEvaluation(
                    evaluated=True,
                    accepted=False,
                    rejection_reason=(
                        BootstrapConfirmationRejectionReason.STABLE_NOT_SELECTED
                    ),
                    pending_before=True,
                    pending_after=False,
                    lifecycle_before=state.lifecycle,
                    lifecycle_after=reset_state.lifecycle,
                    selected_stable=False,
                    provisional_region=pending.terminal_region,
                    candidates_in_region=(),
                    candidate_count=0,
                    overlay_conflict=False,
                    resulting_status=CurrentCandleIdentityStatus.UNAVAILABLE,
                ),
                tracking_terminal=TrackingTerminalEvaluation.not_evaluated(),
            )
            return self._seed_bootstrap(
                reset_state,
                context,
                reset_reason=CurrentCandleIdentityResetReason.ROLL_OVER_INCONSISTENT,
                sequence_match=sequence_match,
                telemetry=telemetry,
            )
        terminal_candidates = self._terminal_members(
            context.member_candles,
            pending.terminal_region,
        )
        if len(terminal_candidates) != 1:
            next_state = replace(state, previous_context=context)
            telemetry = self._bootstrap_confirmation_telemetry(
                state=state,
                next_state=next_state,
                pending=pending,
                candidates=terminal_candidates,
                accepted=False,
                rejection_reason=(
                    BootstrapConfirmationRejectionReason.TERMINAL_CANDIDATE_NOT_UNIQUE
                ),
                overlay_conflict=False,
                resulting_status=CurrentCandleIdentityStatus.AMBIGUOUS,
            )
            return next_state, self._nonconclusive_resolution(
                status=CurrentCandleIdentityStatus.AMBIGUOUS,
                context=context,
                state=next_state,
                diagnostic="bootstrap_terminal_candidate_not_unique",
                sequence_match=sequence_match,
                terminal_region=pending.terminal_region,
                rollover_suspected=True,
                telemetry=telemetry,
            )
        candidate = terminal_candidates[0]
        if self._candidate_is_expiry_overlay(context, candidate.candidate_id):
            next_state = replace(state, previous_context=context)
            telemetry = self._bootstrap_confirmation_telemetry(
                state=state,
                next_state=next_state,
                pending=pending,
                candidates=terminal_candidates,
                accepted=False,
                rejection_reason=(
                    BootstrapConfirmationRejectionReason.OVERLAY_CONFLICT
                ),
                overlay_conflict=True,
                resulting_status=CurrentCandleIdentityStatus.AMBIGUOUS,
            )
            return next_state, self._nonconclusive_resolution(
                status=CurrentCandleIdentityStatus.AMBIGUOUS,
                context=context,
                state=next_state,
                diagnostic="bootstrap_terminal_conflicts_with_overlay",
                sequence_match=sequence_match,
                terminal_region=pending.terminal_region,
                rollover_suspected=True,
                telemetry=telemetry,
            )
        learned_region = self._learn_terminal_region(
            candidate=candidate,
            context=context,
            generation=state.continuity_generation,
            frame_ids=(
                *pending.terminal_region.learned_from_frame_ids,
                context.frame_id,
            ),
        )
        tracking = replace(
            state,
            lifecycle=CurrentCandleIdentityLifecycle.TRACKING,
            previous_context=context,
            terminal_region=learned_region,
            pending_bootstrap=None,
        )
        telemetry = self._bootstrap_confirmation_telemetry(
            state=state,
            next_state=tracking,
            pending=pending,
            candidates=terminal_candidates,
            accepted=True,
            rejection_reason=None,
            overlay_conflict=False,
            resulting_status=CurrentCandleIdentityStatus.CONFIRMED,
        )
        return tracking, self._confirmed_resolution(
            context=context,
            state=tracking,
            candidate=candidate,
            source=CurrentCandleIdentitySource.BOOTSTRAP_CONFIRMATION,
            sequence_match=sequence_match,
            rollover_suspected=True,
            rollover_confirmed=True,
            diagnostic="stable_frame_confirmed_bootstrap_terminal",
            telemetry=telemetry,
        )

    def _resolve_tracking(
        self,
        state: _ResolverState,
        context: CurrentCandleFrameContext,
        sequence_match: CurrentCandleSequenceMatch,
    ) -> tuple[_ResolverState, CurrentCandleIdentityResolution]:
        region = state.terminal_region
        assert region is not None
        if sequence_match.status is CurrentCandleMatchStatus.AMBIGUOUS:
            next_state = self._revalidation_state(state, context)
            telemetry = self._tracking_telemetry(
                trusted_rollover=self._evaluate_temporal_rollover(
                    state.previous_context,
                    context,
                    sequence_match,
                ),
                terminal_seed=TerminalSeedEvaluation.not_evaluated(),
                region_before=region,
                region_after=region,
                sequence_match=sequence_match,
                candidates=(),
                competitors=(),
                overlay_conflict=False,
                missing=None,
                resulting_status=CurrentCandleIdentityStatus.AMBIGUOUS,
                reason=(
                    TrackingTerminalDecisionReason.REGION_PRESERVED_MATCH_AMBIGUOUS
                ),
            )
            return next_state, self._nonconclusive_resolution(
                status=CurrentCandleIdentityStatus.AMBIGUOUS,
                context=context,
                state=next_state,
                diagnostic="tracking_translation_ambiguous",
                sequence_match=sequence_match,
                terminal_region=region,
                telemetry=telemetry,
            )
        if sequence_match.status is not CurrentCandleMatchStatus.SELECTED:
            next_state = self._revalidation_state(state, context)
            telemetry = self._tracking_telemetry(
                trusted_rollover=self._evaluate_temporal_rollover(
                    state.previous_context,
                    context,
                    sequence_match,
                ),
                terminal_seed=TerminalSeedEvaluation.not_evaluated(),
                region_before=region,
                region_after=region,
                sequence_match=sequence_match,
                candidates=(),
                competitors=(),
                overlay_conflict=False,
                missing=None,
                resulting_status=CurrentCandleIdentityStatus.UNAVAILABLE,
                reason=(
                    TrackingTerminalDecisionReason.REGION_PRESERVED_MATCH_UNAVAILABLE
                ),
            )
            return next_state, self._unavailable_resolution(
                context=context,
                state=next_state,
                diagnostic="tracking_translation_unavailable_region_preserved",
                sequence_match=sequence_match,
                terminal_region=region,
                telemetry=telemetry,
            )
        if (
            sequence_match.selected_hypothesis
            is CurrentCandleTranslationHypothesis.ROLLOVER
        ):
            return self._resolve_tracking_rollover(
                state,
                context,
                sequence_match,
                region,
            )
        return self._resolve_tracking_stable(
            state,
            context,
            sequence_match,
            region,
        )

    def _resolve_tracking_stable(
        self,
        state: _ResolverState,
        context: CurrentCandleFrameContext,
        sequence_match: CurrentCandleSequenceMatch,
        region: TerminalSlotRegion,
    ) -> tuple[_ResolverState, CurrentCandleIdentityResolution]:
        trusted_rollover = self._evaluate_temporal_rollover(
            state.previous_context,
            context,
            sequence_match,
        )
        terminal_members = self._terminal_members(context.member_candles, region)
        if len(terminal_members) > 1:
            next_state = self._revalidation_state(state, context)
            telemetry = self._tracking_telemetry(
                trusted_rollover=trusted_rollover,
                terminal_seed=TerminalSeedEvaluation.not_evaluated(),
                region_before=region,
                region_after=region,
                sequence_match=sequence_match,
                candidates=terminal_members,
                competitors=(),
                overlay_conflict=False,
                missing=None,
                resulting_status=CurrentCandleIdentityStatus.AMBIGUOUS,
                reason=(
                    TrackingTerminalDecisionReason.REGION_PRESERVED_MULTIPLE_CANDIDATES
                ),
            )
            return next_state, self._nonconclusive_resolution(
                status=CurrentCandleIdentityStatus.AMBIGUOUS,
                context=context,
                state=next_state,
                diagnostic="multiple_members_compete_for_terminal_slot",
                sequence_match=sequence_match,
                terminal_region=region,
                telemetry=telemetry,
            )
        competitors = self._terminal_competitors(context, region)
        if competitors:
            next_state = self._revalidation_state(state, context)
            telemetry = self._tracking_telemetry(
                trusted_rollover=trusted_rollover,
                terminal_seed=TerminalSeedEvaluation.not_evaluated(),
                region_before=region,
                region_after=region,
                sequence_match=sequence_match,
                candidates=terminal_members,
                competitors=competitors,
                overlay_conflict=False,
                missing=None,
                resulting_status=CurrentCandleIdentityStatus.AMBIGUOUS,
                reason=(
                    TrackingTerminalDecisionReason.REGION_PRESERVED_COMPETITOR
                ),
            )
            return next_state, self._nonconclusive_resolution(
                status=CurrentCandleIdentityStatus.AMBIGUOUS,
                context=context,
                state=next_state,
                diagnostic="excluded_candle_like_terminal_competitor",
                sequence_match=sequence_match,
                terminal_region=region,
                telemetry=telemetry,
            )
        if terminal_members:
            candidate = terminal_members[0]
            if self._candidate_is_expiry_overlay(context, candidate.candidate_id):
                next_state = self._revalidation_state(state, context)
                telemetry = self._tracking_telemetry(
                    trusted_rollover=trusted_rollover,
                    terminal_seed=TerminalSeedEvaluation.not_evaluated(),
                    region_before=region,
                    region_after=region,
                    sequence_match=sequence_match,
                    candidates=terminal_members,
                    competitors=(),
                    overlay_conflict=True,
                    missing=None,
                    resulting_status=CurrentCandleIdentityStatus.AMBIGUOUS,
                    reason=TrackingTerminalDecisionReason.REGION_PRESERVED_OVERLAY,
                )
                return next_state, self._nonconclusive_resolution(
                    status=CurrentCandleIdentityStatus.AMBIGUOUS,
                    context=context,
                    state=next_state,
                    diagnostic="tracked_terminal_conflicts_with_overlay",
                    sequence_match=sequence_match,
                    terminal_region=region,
                    telemetry=telemetry,
                )
            updated_region = self._learn_terminal_region(
                candidate=candidate,
                context=context,
                generation=state.continuity_generation,
                frame_ids=self._append_frame_id(
                    region.learned_from_frame_ids,
                    context.frame_id,
                ),
            )
            next_state = replace(
                state,
                lifecycle=CurrentCandleIdentityLifecycle.TRACKING,
                previous_context=context,
                terminal_region=updated_region,
            )
            telemetry = self._tracking_telemetry(
                trusted_rollover=trusted_rollover,
                terminal_seed=TerminalSeedEvaluation.not_evaluated(),
                region_before=region,
                region_after=updated_region,
                sequence_match=sequence_match,
                candidates=terminal_members,
                competitors=(),
                overlay_conflict=False,
                missing=None,
                resulting_status=CurrentCandleIdentityStatus.CONFIRMED,
                reason=(
                    TrackingTerminalDecisionReason.REGION_UPDATED_FROM_STABLE
                ),
                region_moved=self._region_geometry_changed(
                    region,
                    updated_region,
                ),
            )
            return next_state, self._confirmed_resolution(
                context=context,
                state=next_state,
                candidate=candidate,
                source=CurrentCandleIdentitySource.STABLE_TRACKING,
                sequence_match=sequence_match,
                rollover_suspected=False,
                rollover_confirmed=False,
                diagnostic="terminal_candidate_confirmed_by_stable_tracking",
                telemetry=telemetry,
            )

        missing = self._missing_evidence(context, region)
        if missing.sufficient:
            next_state = replace(
                state,
                lifecycle=CurrentCandleIdentityLifecycle.TRACKING,
                previous_context=context,
            )
            telemetry = self._tracking_telemetry(
                trusted_rollover=trusted_rollover,
                terminal_seed=TerminalSeedEvaluation.not_evaluated(),
                region_before=region,
                region_after=region,
                sequence_match=sequence_match,
                candidates=(),
                competitors=(),
                overlay_conflict=False,
                missing=missing,
                resulting_status=CurrentCandleIdentityStatus.MISSING_FROM_VIEW,
                reason=(
                    TrackingTerminalDecisionReason.REGION_PRESERVED_MISSING_FROM_VIEW
                ),
            )
            return next_state, self._missing_resolution(
                context=context,
                state=next_state,
                sequence_match=sequence_match,
                missing_evidence=missing,
                telemetry=telemetry,
            )
        next_state = self._revalidation_state(state, context)
        telemetry = self._tracking_telemetry(
            trusted_rollover=trusted_rollover,
            terminal_seed=TerminalSeedEvaluation.not_evaluated(),
            region_before=region,
            region_after=region,
            sequence_match=sequence_match,
            candidates=(),
            competitors=(),
            overlay_conflict=False,
            missing=missing,
            resulting_status=CurrentCandleIdentityStatus.AMBIGUOUS,
            reason=(
                TrackingTerminalDecisionReason.REGION_PRESERVED_MISSING_INSUFFICIENT
            ),
        )
        return next_state, self._nonconclusive_resolution(
            status=CurrentCandleIdentityStatus.AMBIGUOUS,
            context=context,
            state=next_state,
            diagnostic="terminal_slot_absence_not_uniquely_explained",
            sequence_match=sequence_match,
            terminal_region=region,
            missing_evidence=missing,
            telemetry=telemetry,
        )

    def _resolve_tracking_rollover(
        self,
        state: _ResolverState,
        context: CurrentCandleFrameContext,
        sequence_match: CurrentCandleSequenceMatch,
        region: TerminalSlotRegion,
    ) -> tuple[_ResolverState, CurrentCandleIdentityResolution]:
        trusted_rollover = self._evaluate_temporal_rollover(
            state.previous_context,
            context,
            sequence_match,
        )
        terminal_members = self._terminal_members(context.member_candles, region)
        competitors = self._terminal_competitors(context, region)
        terminal_seed = (
            self._evaluate_terminal_seed(
                context=context,
                trusted_rollover=trusted_rollover,
            )
            if trusted_rollover.temporal_rollover_trusted
            else TerminalSeedEvaluation.not_evaluated()
        )
        if not trusted_rollover.temporal_rollover_trusted:
            next_state = self._revalidation_state(state, context)
            telemetry = self._tracking_telemetry(
                trusted_rollover=trusted_rollover,
                terminal_seed=terminal_seed,
                region_before=region,
                region_after=region,
                sequence_match=sequence_match,
                candidates=terminal_members,
                competitors=competitors,
                overlay_conflict=False,
                missing=None,
                resulting_status=CurrentCandleIdentityStatus.AMBIGUOUS,
                reason=(
                    TrackingTerminalDecisionReason.REGION_PRESERVED_ROLLOVER_REJECTED
                ),
            )
            return next_state, self._nonconclusive_resolution(
                status=CurrentCandleIdentityStatus.AMBIGUOUS,
                context=context,
                state=next_state,
                diagnostic="rollover_not_trusted_during_tracking",
                sequence_match=sequence_match,
                terminal_region=region,
                rollover_suspected=True,
                telemetry=telemetry,
            )
        if terminal_seed.status is not TerminalSeedEvaluationStatus.OBSERVED:
            missing = (
                self._missing_evidence(context, region)
                if not terminal_members and not competitors
                else None
            )
            next_state = self._revalidation_state(state, context)
            reason = (
                TrackingTerminalDecisionReason.REGION_PRESERVED_OVERLAY
                if terminal_seed.status is TerminalSeedEvaluationStatus.OVERLAY
                else (
                    TrackingTerminalDecisionReason.REGION_PRESERVED_ROLLOVER_TERMINAL_ABSENT
                )
            )
            telemetry = self._tracking_telemetry(
                trusted_rollover=trusted_rollover,
                terminal_seed=terminal_seed,
                region_before=region,
                region_after=region,
                sequence_match=sequence_match,
                candidates=terminal_members,
                competitors=competitors,
                overlay_conflict=(
                    terminal_seed.status is TerminalSeedEvaluationStatus.OVERLAY
                ),
                missing=missing,
                resulting_status=CurrentCandleIdentityStatus.AMBIGUOUS,
                reason=reason,
            )
            return next_state, self._nonconclusive_resolution(
                status=CurrentCandleIdentityStatus.AMBIGUOUS,
                context=context,
                state=next_state,
                diagnostic="trusted_rollover_terminal_not_observed_region_preserved",
                sequence_match=sequence_match,
                terminal_region=region,
                rollover_suspected=True,
                missing_evidence=missing,
                telemetry=telemetry,
            )
        assert terminal_seed.candidate_id is not None
        candidate = self._member_by_id(context, terminal_seed.candidate_id)
        candidate_in_region = region.contains(candle_center_x(candidate))
        only_observed_terminal = (
            len(terminal_members) == 1
            and terminal_members[0].candidate_id == candidate.candidate_id
        )
        if not candidate_in_region or not only_observed_terminal:
            next_state = self._revalidation_state(state, context)
            reason = (
                TrackingTerminalDecisionReason.REGION_PRESERVED_ROLLOVER_TERMINAL_OUTSIDE
                if not candidate_in_region
                else TrackingTerminalDecisionReason.REGION_PRESERVED_MULTIPLE_CANDIDATES
            )
            telemetry = self._tracking_telemetry(
                trusted_rollover=trusted_rollover,
                terminal_seed=terminal_seed,
                region_before=region,
                region_after=region,
                sequence_match=sequence_match,
                candidates=terminal_members,
                competitors=competitors,
                overlay_conflict=False,
                missing=None,
                resulting_status=CurrentCandleIdentityStatus.AMBIGUOUS,
                reason=reason,
            )
            return next_state, self._nonconclusive_resolution(
                status=CurrentCandleIdentityStatus.AMBIGUOUS,
                context=context,
                state=next_state,
                diagnostic="rollover_terminal_not_unique_in_confirmed_region",
                sequence_match=sequence_match,
                terminal_region=region,
                rollover_suspected=True,
                telemetry=telemetry,
            )
        if competitors:
            next_state = self._revalidation_state(state, context)
            telemetry = self._tracking_telemetry(
                trusted_rollover=trusted_rollover,
                terminal_seed=terminal_seed,
                region_before=region,
                region_after=region,
                sequence_match=sequence_match,
                candidates=terminal_members,
                competitors=competitors,
                overlay_conflict=False,
                missing=None,
                resulting_status=CurrentCandleIdentityStatus.AMBIGUOUS,
                reason=TrackingTerminalDecisionReason.REGION_PRESERVED_COMPETITOR,
            )
            return next_state, self._nonconclusive_resolution(
                status=CurrentCandleIdentityStatus.AMBIGUOUS,
                context=context,
                state=next_state,
                diagnostic="excluded_candle_like_terminal_competitor",
                sequence_match=sequence_match,
                terminal_region=region,
                rollover_suspected=True,
                telemetry=telemetry,
            )
        updated_region = self._learn_terminal_region(
            candidate=candidate,
            context=context,
            generation=state.continuity_generation,
            frame_ids=self._append_frame_id(
                region.learned_from_frame_ids,
                context.frame_id,
            ),
        )
        next_state = replace(
            state,
            lifecycle=CurrentCandleIdentityLifecycle.TRACKING,
            previous_context=context,
            terminal_region=updated_region,
        )
        telemetry = self._tracking_telemetry(
            trusted_rollover=trusted_rollover,
            terminal_seed=terminal_seed,
            region_before=region,
            region_after=updated_region,
            sequence_match=sequence_match,
            candidates=terminal_members,
            competitors=(),
            overlay_conflict=False,
            missing=None,
            resulting_status=CurrentCandleIdentityStatus.CONFIRMED,
            reason=(
                TrackingTerminalDecisionReason.REGION_UPDATED_FROM_ROLLOVER_TERMINAL
            ),
            region_moved=self._region_geometry_changed(
                region,
                updated_region,
            ),
        )
        return next_state, self._confirmed_resolution(
            context=context,
            state=next_state,
            candidate=candidate,
            source=CurrentCandleIdentitySource.TRUSTED_ROLLOVER,
            sequence_match=sequence_match,
            rollover_suspected=True,
            rollover_confirmed=True,
            diagnostic="terminal_candidate_confirmed_by_trusted_rollover",
            telemetry=telemetry,
        )

    def _seed_bootstrap(
        self,
        state: _ResolverState,
        context: CurrentCandleFrameContext,
        *,
        reset_reason: CurrentCandleIdentityResetReason | None = None,
        sequence_match: CurrentCandleSequenceMatch | None = None,
        telemetry: _ResolutionTelemetry | None = None,
    ) -> tuple[_ResolverState, CurrentCandleIdentityResolution]:
        if not self._membership_available(context):
            degraded = replace(
                state,
                lifecycle=CurrentCandleIdentityLifecycle.DEGRADED,
            )
            return degraded, self._unavailable_resolution(
                context=context,
                state=degraded,
                diagnostic="bootstrap_membership_unavailable",
                reset_reason=(
                    reset_reason
                    or CurrentCandleIdentityResetReason.MEMBERSHIP_UNAVAILABLE
                ),
                sequence_match=sequence_match,
                telemetry=telemetry,
            )
        seeded = replace(
            state,
            lifecycle=CurrentCandleIdentityLifecycle.BOOTSTRAPPING,
            previous_context=context,
            terminal_region=None,
            pending_bootstrap=None,
        )
        return seeded, self._unavailable_resolution(
            context=context,
            state=seeded,
            diagnostic="bootstrap_requires_trusted_rollover_then_stable_frame",
            reset_reason=reset_reason,
            sequence_match=sequence_match,
            telemetry=telemetry,
        )

    def _confirmed_resolution(
        self,
        *,
        context: CurrentCandleFrameContext,
        state: _ResolverState,
        candidate: FinalCandleTrace,
        source: CurrentCandleIdentitySource,
        sequence_match: CurrentCandleSequenceMatch,
        rollover_suspected: bool,
        rollover_confirmed: bool,
        diagnostic: str,
        telemetry: _ResolutionTelemetry | None = None,
    ) -> CurrentCandleIdentityResolution:
        metrics = sequence_match.selected_metrics
        region = state.terminal_region
        assert region is not None
        evidence = CurrentCandleIdentityEvidence(
            matched_historical_member_count=metrics.matched_historical_member_count,
            type_match_ratio=metrics.type_match_ratio,
            terminal_candidate_ids=(candidate.candidate_id,),
            sufficient=True,
        )
        result = CurrentCandleIdentityResult(
            status=CurrentCandleIdentityStatus.CONFIRMED,
            candidate_id=candidate.candidate_id,
            source=source,
            terminal_region=region,
            estimated_pitch_px=context.estimated_pitch_px,
            continuity_generation=state.continuity_generation,
            evidence=evidence,
            diagnostics=(diagnostic,),
        )
        return CurrentCandleIdentityResolution(
            result=result,
            trace=self._trace(
                context=context,
                state=state,
                status=result.status,
                sequence_match=sequence_match,
                terminal_region=region,
                rollover_suspected=rollover_suspected,
                rollover_confirmed=rollover_confirmed,
                chosen_candidate_id=candidate.candidate_id,
                diagnostic=diagnostic,
                telemetry=telemetry,
            ),
        )

    def _missing_resolution(
        self,
        *,
        context: CurrentCandleFrameContext,
        state: _ResolverState,
        sequence_match: CurrentCandleSequenceMatch,
        missing_evidence: CurrentCandleMissingEvidence,
        telemetry: _ResolutionTelemetry | None = None,
    ) -> CurrentCandleIdentityResolution:
        metrics = sequence_match.selected_metrics
        region = state.terminal_region
        assert region is not None
        evidence = CurrentCandleIdentityEvidence(
            matched_historical_member_count=metrics.matched_historical_member_count,
            type_match_ratio=metrics.type_match_ratio,
            terminal_candidate_ids=(),
            sufficient=missing_evidence.sufficient,
        )
        diagnostic = "learned_terminal_slot_missing_from_view"
        result = CurrentCandleIdentityResult(
            status=CurrentCandleIdentityStatus.MISSING_FROM_VIEW,
            candidate_id=None,
            source=CurrentCandleIdentitySource.TERMINAL_SLOT_EMPTY,
            terminal_region=region,
            estimated_pitch_px=context.estimated_pitch_px,
            continuity_generation=state.continuity_generation,
            evidence=evidence,
            diagnostics=(diagnostic,),
        )
        return CurrentCandleIdentityResolution(
            result=result,
            trace=self._trace(
                context=context,
                state=state,
                status=result.status,
                sequence_match=sequence_match,
                terminal_region=region,
                missing_evidence=missing_evidence,
                diagnostic=diagnostic,
                telemetry=telemetry,
            ),
        )

    def _unavailable_resolution(
        self,
        *,
        context: CurrentCandleFrameContext,
        state: _ResolverState,
        diagnostic: str,
        reset_reason: CurrentCandleIdentityResetReason | None = None,
        sequence_match: CurrentCandleSequenceMatch | None = None,
        terminal_region: TerminalSlotRegion | None = None,
        rollover_suspected: bool = False,
        telemetry: _ResolutionTelemetry | None = None,
    ) -> CurrentCandleIdentityResolution:
        return self._nonconclusive_resolution(
            status=CurrentCandleIdentityStatus.UNAVAILABLE,
            context=context,
            state=state,
            diagnostic=diagnostic,
            reset_reason=reset_reason,
            sequence_match=sequence_match,
            terminal_region=terminal_region,
            rollover_suspected=rollover_suspected,
            telemetry=telemetry,
        )

    def _nonconclusive_resolution(
        self,
        *,
        status: CurrentCandleIdentityStatus,
        context: CurrentCandleFrameContext,
        state: _ResolverState,
        diagnostic: str,
        reset_reason: CurrentCandleIdentityResetReason | None = None,
        sequence_match: CurrentCandleSequenceMatch | None = None,
        terminal_region: TerminalSlotRegion | None = None,
        rollover_suspected: bool = False,
        missing_evidence: CurrentCandleMissingEvidence | None = None,
        telemetry: _ResolutionTelemetry | None = None,
    ) -> CurrentCandleIdentityResolution:
        if status not in (
            CurrentCandleIdentityStatus.UNAVAILABLE,
            CurrentCandleIdentityStatus.AMBIGUOUS,
        ):
            raise ValueError("El helper solo construye resultados no concluyentes.")
        effective_region = terminal_region or state.terminal_region
        result = CurrentCandleIdentityResult(
            status=status,
            candidate_id=None,
            source=CurrentCandleIdentitySource.NONE,
            terminal_region=effective_region,
            estimated_pitch_px=context.estimated_pitch_px,
            continuity_generation=state.continuity_generation,
            evidence=None,
            diagnostics=(diagnostic,),
        )
        return CurrentCandleIdentityResolution(
            result=result,
            trace=self._trace(
                context=context,
                state=state,
                status=status,
                sequence_match=sequence_match,
                terminal_region=effective_region,
                rollover_suspected=rollover_suspected,
                missing_evidence=missing_evidence,
                reset_reason=reset_reason,
                diagnostic=diagnostic,
                telemetry=telemetry,
            ),
        )

    def _trace(
        self,
        *,
        context: CurrentCandleFrameContext,
        state: _ResolverState,
        status: CurrentCandleIdentityStatus,
        diagnostic: str,
        sequence_match: CurrentCandleSequenceMatch | None = None,
        terminal_region: TerminalSlotRegion | None = None,
        rollover_suspected: bool = False,
        rollover_confirmed: bool = False,
        chosen_candidate_id: str | None = None,
        missing_evidence: CurrentCandleMissingEvidence | None = None,
        reset_reason: CurrentCandleIdentityResetReason | None = None,
        telemetry: _ResolutionTelemetry | None = None,
    ) -> CurrentCandleIdentityTrace:
        effective_telemetry = telemetry or _ResolutionTelemetry.empty()
        legacy_latest = (
            context.membership.latest_candidate_id
            if context.membership is not None
            else None
        )
        return CurrentCandleIdentityTrace(
            frame_id=context.frame_id,
            wall_timestamp=context.wall_timestamp,
            monotonic_timestamp=context.monotonic_timestamp,
            source_key=context.source_key,
            session_key=context.session_key,
            status=status,
            internal_state=state.lifecycle,
            continuity_generation=state.continuity_generation,
            legacy_latest_candidate_id=legacy_latest,
            terminal_region=terminal_region,
            estimated_pitch_px=context.estimated_pitch_px,
            sequence_match=sequence_match,
            rollover_suspected=rollover_suspected,
            rollover_confirmed=rollover_confirmed,
            chosen_candidate_id=chosen_candidate_id,
            missing_evidence=missing_evidence,
            reset_reason=reset_reason,
            expiry_evidence_consistent=context.expiry_evidence_consistent,
            expiry_vertical_line_x=context.expiry_vertical_line_x,
            expiry_vertical_line_conflict=(
                context.expiry_vertical_line_conflict
            ),
            diagnostics=(diagnostic,),
            expiry_vertical_line_start_y=(
                context.expiry_vertical_line_start_y
            ),
            expiry_vertical_line_end_y=context.expiry_vertical_line_end_y,
            trusted_rollover_evaluation=(
                effective_telemetry.trusted_rollover
            ),
            terminal_seed_evaluation=effective_telemetry.terminal_seed,
            bootstrap_confirmation_evaluation=(
                effective_telemetry.bootstrap_confirmation
            ),
            tracking_terminal_evaluation=(
                effective_telemetry.tracking_terminal
            ),
        )

    def _missing_evidence(
        self,
        context: CurrentCandleFrameContext,
        region: TerminalSlotRegion,
    ) -> CurrentCandleMissingEvidence:
        members = context.member_candles
        previous = members[-1] if members else None
        pitch = context.estimated_pitch_px
        distance = None
        fully_observable = False
        if previous is not None and pitch is not None:
            distance = (region.center_x_roi - candle_center_x(previous)) / pitch
            observability = previous.observability
            if observability is not None:
                fully_observable = (
                    observability.fully_observable_close_for(previous.candle_type)
                    is True
                )
        close_to_previous_slot = (
            distance is not None
            and abs(distance - 1.0)
            <= self._config.missing_previous_slot_tolerance_pitch_ratio
        )
        return CurrentCandleMissingEvidence(
            terminal_region_valid=True,
            terminal_member_absent=True,
            previous_slot_candidate_id=(
                previous.candidate_id if close_to_previous_slot and previous else None
            ),
            previous_slot_fully_observable=fully_observable,
            previous_slot_distance_in_pitch_units=(
                distance if close_to_previous_slot else None
            ),
            candle_like_competitor_ids=self._terminal_competitors(context, region),
        )

    def _terminal_competitors(
        self,
        context: CurrentCandleFrameContext,
        region: TerminalSlotRegion,
    ) -> tuple[str, ...]:
        member_ids = {candle.candidate_id for candle in context.member_candles}
        overlay_by_id = (
            context.overlay_evidence.by_candidate_id()
            if context.overlay_evidence is not None
            else {}
        )
        competitors = []
        for candle in context.final_candles:
            if candle.candidate_id in member_ids or not region.contains(
                candle_center_x(candle)
            ):
                continue
            overlay = overlay_by_id.get(candle.candidate_id)
            if (
                overlay is not None
                and overlay.status is CandleOverlayEvidenceStatus.EXPIRY_OVERLAY
            ):
                continue
            competitors.append(candle.candidate_id)
        return tuple(competitors)

    @staticmethod
    def _candidate_is_expiry_overlay(
        context: CurrentCandleFrameContext,
        candidate_id: str,
    ) -> bool:
        if context.overlay_evidence is None:
            return False
        evidence = context.overlay_evidence.by_candidate_id().get(candidate_id)
        return (
            evidence is not None
            and evidence.status is CandleOverlayEvidenceStatus.EXPIRY_OVERLAY
        )

    def _evaluate_temporal_rollover(
        self,
        previous: CurrentCandleFrameContext | None,
        current: CurrentCandleFrameContext,
        sequence_match: CurrentCandleSequenceMatch,
    ) -> TrustedRolloverEvaluation:
        if previous is None:
            return TrustedRolloverEvaluation.not_evaluated(
                TemporalRolloverRejectionReason.PREVIOUS_CONTEXT_UNAVAILABLE
            )
        if not self._membership_available(previous):
            return TrustedRolloverEvaluation.not_evaluated(
                TemporalRolloverRejectionReason.PREVIOUS_MEMBERSHIP_UNAVAILABLE
            )
        if not self._membership_available(current):
            return TrustedRolloverEvaluation.not_evaluated(
                TemporalRolloverRejectionReason.CURRENT_MEMBERSHIP_UNAVAILABLE
            )
        metrics = sequence_match.rollover
        previous_ids = tuple(candle.candidate_id for candle in previous.member_candles)
        current_ids = tuple(candle.candidate_id for candle in current.member_candles)
        expected_previous = previous_ids[0]
        expected_current = current_ids[-1]
        unmatched_previous = metrics.unmatched_previous_candidate_ids
        unmatched_current = metrics.unmatched_current_candidate_ids
        previous_boundary_compatible = unmatched_previous in (
            (),
            (expected_previous,),
        )
        current_boundary_compatible = unmatched_current in (
            (),
            (expected_current,),
        )
        support_pass = (
            metrics.matched_historical_member_count
            >= self._config.minimum_historical_matches
        )
        type_ratio_pass = (
            metrics.type_match_ratio >= self._config.minimum_type_match_ratio
        )
        pitch = current.estimated_pitch_px
        assert pitch is not None
        maximum_residual = (
            pitch * self._config.maximum_match_residual_pitch_ratio
        )
        residual_pass = (
            metrics.maximum_residual_px is not None
            and metrics.maximum_residual_px <= maximum_residual
        )
        rejection_reason: TemporalRolloverRejectionReason | None = None
        if sequence_match.status is not CurrentCandleMatchStatus.SELECTED:
            rejection_reason = TemporalRolloverRejectionReason.MATCH_NOT_SELECTED
        elif (
            sequence_match.selected_hypothesis
            is not CurrentCandleTranslationHypothesis.ROLLOVER
        ):
            rejection_reason = (
                TemporalRolloverRejectionReason.SELECTED_HYPOTHESIS_NOT_ROLLOVER
            )
        elif not support_pass:
            rejection_reason = TemporalRolloverRejectionReason.SUPPORT_BELOW_MINIMUM
        elif not type_ratio_pass:
            rejection_reason = (
                TemporalRolloverRejectionReason.TYPE_RATIO_BELOW_MINIMUM
            )
        elif metrics.maximum_residual_px is None:
            rejection_reason = TemporalRolloverRejectionReason.RESIDUAL_UNAVAILABLE
        elif not residual_pass:
            rejection_reason = TemporalRolloverRejectionReason.RESIDUAL_ABOVE_MAXIMUM
        elif not metrics.qualifies:
            rejection_reason = TemporalRolloverRejectionReason.ROLLOVER_NOT_QUALIFIED
        elif not previous_boundary_compatible:
            rejection_reason = (
                TemporalRolloverRejectionReason.PREVIOUS_BOUNDARY_INCOMPATIBLE
            )
        elif not current_boundary_compatible:
            rejection_reason = (
                TemporalRolloverRejectionReason.CURRENT_BOUNDARY_INCOMPATIBLE
            )
        elif not unmatched_previous and not unmatched_current:
            rejection_reason = TemporalRolloverRejectionReason.NO_BOUNDARY_CHANGE
        accepted = rejection_reason is None
        return TrustedRolloverEvaluation(
            status=(
                TemporalRolloverEvaluationStatus.ACCEPTED
                if accepted
                else TemporalRolloverEvaluationStatus.REJECTED
            ),
            rejection_reason=rejection_reason,
            match_status=sequence_match.status,
            selected_hypothesis=sequence_match.selected_hypothesis,
            rollover_qualifies=metrics.qualifies,
            support_actual=metrics.matched_historical_member_count,
            support_minimum=self._config.minimum_historical_matches,
            support_pass=support_pass,
            type_ratio_actual=metrics.type_match_ratio,
            type_ratio_minimum=self._config.minimum_type_match_ratio,
            type_ratio_pass=type_ratio_pass,
            residual_actual_px=metrics.maximum_residual_px,
            residual_maximum_px=maximum_residual,
            residual_pass=residual_pass,
            previous_member_count=len(previous_ids),
            current_member_count=len(current_ids),
            unmatched_previous_ids=unmatched_previous,
            unmatched_current_ids=unmatched_current,
            expected_previous_leftmost_id=expected_previous,
            expected_current_rightmost_id=expected_current,
            previous_boundary_compatible=previous_boundary_compatible,
            current_boundary_compatible=current_boundary_compatible,
            temporal_rollover_trusted=accepted,
        )

    def _evaluate_terminal_seed(
        self,
        *,
        context: CurrentCandleFrameContext,
        trusted_rollover: TrustedRolloverEvaluation,
    ) -> TerminalSeedEvaluation:
        if not trusted_rollover.temporal_rollover_trusted:
            return TerminalSeedEvaluation.not_evaluated()
        unmatched = trusted_rollover.unmatched_current_ids
        if not unmatched:
            return TerminalSeedEvaluation(
                status=TerminalSeedEvaluationStatus.ABSENT,
                candidate_id=None,
                provenance=TerminalSeedProvenance.NONE,
                is_unmatched_current=False,
                is_current_rightmost=False,
                membership_included=False,
                geometry_valid=False,
                close_observable=None,
                overlay_status=None,
                diagnostic="trusted_rollover_has_no_unmatched_current_terminal",
            )
        if len(unmatched) != 1:
            return TerminalSeedEvaluation(
                status=TerminalSeedEvaluationStatus.AMBIGUOUS,
                candidate_id=None,
                provenance=TerminalSeedProvenance.NONE,
                is_unmatched_current=True,
                is_current_rightmost=False,
                membership_included=False,
                geometry_valid=False,
                close_observable=None,
                overlay_status=None,
                diagnostic="trusted_rollover_has_multiple_unmatched_current",
            )
        candidate_id = unmatched[0]
        current_rightmost = context.member_candles[-1]
        is_rightmost = candidate_id == current_rightmost.candidate_id
        candidates = tuple(
            candle
            for candle in context.member_candles
            if candle.candidate_id == candidate_id
        )
        membership_included = len(candidates) == 1
        if not is_rightmost or not membership_included:
            return TerminalSeedEvaluation(
                status=TerminalSeedEvaluationStatus.AMBIGUOUS,
                candidate_id=candidate_id,
                provenance=TerminalSeedProvenance.NONE,
                is_unmatched_current=True,
                is_current_rightmost=is_rightmost,
                membership_included=membership_included,
                geometry_valid=False,
                close_observable=None,
                overlay_status=None,
                diagnostic="unmatched_current_is_not_unique_membership_rightmost",
            )
        candidate = candidates[0]
        center = candle_center_x(candidate)
        geometry_valid = (
            candidate.x >= 0
            and candidate.width > 0
            and 0 <= center <= context.roi_width
        )
        observability = candidate.observability
        close_observable = (
            observability.fully_observable_close_for(candidate.candle_type)
            if observability is not None
            else None
        )
        overlay = (
            context.overlay_evidence.by_candidate_id().get(candidate_id)
            if context.overlay_evidence is not None
            else None
        )
        overlay_status = overlay.status if overlay is not None else None
        if overlay_status is CandleOverlayEvidenceStatus.EXPIRY_OVERLAY:
            return TerminalSeedEvaluation(
                status=TerminalSeedEvaluationStatus.OVERLAY,
                candidate_id=candidate_id,
                provenance=TerminalSeedProvenance.UNMATCHED_CURRENT_RIGHTMOST,
                is_unmatched_current=True,
                is_current_rightmost=True,
                membership_included=True,
                geometry_valid=geometry_valid,
                close_observable=close_observable,
                overlay_status=overlay_status,
                diagnostic="unmatched_current_terminal_is_expiry_overlay",
            )
        if not geometry_valid:
            return TerminalSeedEvaluation(
                status=TerminalSeedEvaluationStatus.INVALID_GEOMETRY,
                candidate_id=candidate_id,
                provenance=TerminalSeedProvenance.UNMATCHED_CURRENT_RIGHTMOST,
                is_unmatched_current=True,
                is_current_rightmost=True,
                membership_included=True,
                geometry_valid=False,
                close_observable=close_observable,
                overlay_status=overlay_status,
                diagnostic="unmatched_current_terminal_geometry_invalid",
            )
        return TerminalSeedEvaluation(
            status=TerminalSeedEvaluationStatus.OBSERVED,
            candidate_id=candidate_id,
            provenance=TerminalSeedProvenance.UNMATCHED_CURRENT_RIGHTMOST,
            is_unmatched_current=True,
            is_current_rightmost=True,
            membership_included=True,
            geometry_valid=True,
            close_observable=close_observable,
            overlay_status=overlay_status,
            diagnostic="unmatched_current_rightmost_terminal_observed",
        )

    @staticmethod
    def _member_by_id(
        context: CurrentCandleFrameContext,
        candidate_id: str,
    ) -> FinalCandleTrace:
        matches = tuple(
            candle
            for candle in context.member_candles
            if candle.candidate_id == candidate_id
        )
        if len(matches) != 1:
            raise ValueError("Terminal seed must identify exactly one member.")
        return matches[0]

    @staticmethod
    def _revalidation_state(
        state: _ResolverState,
        context: CurrentCandleFrameContext,
    ) -> _ResolverState:
        return replace(
            state,
            lifecycle=CurrentCandleIdentityLifecycle.DEGRADED,
            previous_context=context,
        )

    @staticmethod
    def _bootstrap_confirmation_telemetry(
        *,
        state: _ResolverState,
        next_state: _ResolverState,
        pending: _PendingBootstrap,
        candidates: tuple[FinalCandleTrace, ...],
        accepted: bool,
        rejection_reason: BootstrapConfirmationRejectionReason | None,
        overlay_conflict: bool,
        resulting_status: CurrentCandleIdentityStatus,
    ) -> _ResolutionTelemetry:
        return _ResolutionTelemetry(
            trusted_rollover=TrustedRolloverEvaluation.not_evaluated(),
            terminal_seed=TerminalSeedEvaluation.not_evaluated(),
            bootstrap_confirmation=BootstrapConfirmationEvaluation(
                evaluated=True,
                accepted=accepted,
                rejection_reason=rejection_reason,
                pending_before=True,
                pending_after=next_state.pending_bootstrap is not None,
                lifecycle_before=state.lifecycle,
                lifecycle_after=next_state.lifecycle,
                selected_stable=True,
                provisional_region=pending.terminal_region,
                candidates_in_region=tuple(
                    candidate.candidate_id for candidate in candidates
                ),
                candidate_count=len(candidates),
                overlay_conflict=overlay_conflict,
                resulting_status=resulting_status,
            ),
            tracking_terminal=TrackingTerminalEvaluation.not_evaluated(),
        )

    @staticmethod
    def _tracking_telemetry(
        *,
        trusted_rollover: TrustedRolloverEvaluation,
        terminal_seed: TerminalSeedEvaluation,
        region_before: TerminalSlotRegion,
        region_after: TerminalSlotRegion,
        sequence_match: CurrentCandleSequenceMatch,
        candidates: tuple[FinalCandleTrace, ...],
        competitors: tuple[str, ...],
        overlay_conflict: bool,
        missing: CurrentCandleMissingEvidence | None,
        resulting_status: CurrentCandleIdentityStatus,
        reason: TrackingTerminalDecisionReason,
        region_moved: bool = False,
    ) -> _ResolutionTelemetry:
        return _ResolutionTelemetry(
            trusted_rollover=trusted_rollover,
            terminal_seed=terminal_seed,
            bootstrap_confirmation=BootstrapConfirmationEvaluation.not_evaluated(),
            tracking_terminal=TrackingTerminalEvaluation(
                evaluated=True,
                region_before=region_before,
                region_after=region_after,
                selected_hypothesis=sequence_match.selected_hypothesis,
                candidates_in_region=tuple(
                    candidate.candidate_id for candidate in candidates
                ),
                rollover_terminal_status=terminal_seed.status,
                candidate_provenance=terminal_seed.provenance,
                competitor_ids=competitors,
                overlay_conflict=overlay_conflict,
                missing_evidence=missing,
                resulting_status=resulting_status,
                region_moved=region_moved,
                decision_reason=reason,
            ),
        )

    @staticmethod
    def _region_geometry_changed(
        before: TerminalSlotRegion,
        after: TerminalSlotRegion,
    ) -> bool:
        """Return whether authoritative terminal geometry actually moved."""

        return any(
            not isclose(before_value, after_value, rel_tol=0.0, abs_tol=1e-9)
            for before_value, after_value in (
                (before.center_x_roi, after.center_x_roi),
                (before.lower_x_roi, after.lower_x_roi),
                (before.upper_x_roi, after.upper_x_roi),
                (before.normalized_center_x, after.normalized_center_x),
                (before.estimated_pitch_px, after.estimated_pitch_px),
            )
        )

    def _learn_terminal_region(
        self,
        *,
        candidate: FinalCandleTrace,
        context: CurrentCandleFrameContext,
        generation: int,
        frame_ids: tuple[int, ...],
    ) -> TerminalSlotRegion:
        pitch = context.estimated_pitch_px
        assert pitch is not None
        center = candle_center_x(candidate)
        half_width = max(
            pitch * self._config.terminal_region_half_width_pitch_ratio,
            candidate.width * self._config.terminal_region_width_margin_ratio,
        )
        return TerminalSlotRegion(
            center_x_roi=center,
            lower_x_roi=max(0.0, center - half_width),
            upper_x_roi=min(float(context.roi_width), center + half_width),
            normalized_center_x=center / context.roi_width,
            estimated_pitch_px=pitch,
            continuity_generation=generation,
            learned_from_frame_ids=frame_ids,
        )

    @staticmethod
    def _terminal_members(
        members: tuple[FinalCandleTrace, ...],
        region: TerminalSlotRegion,
    ) -> tuple[FinalCandleTrace, ...]:
        return tuple(
            candle for candle in members if region.contains(candle_center_x(candle))
        )

    def _continuity_problem(
        self,
        previous: CurrentCandleFrameContext,
        current: CurrentCandleFrameContext,
    ) -> CurrentCandleIdentityResetReason | None:
        if current.frame_id - previous.frame_id > self._config.maximum_frame_id_step:
            return CurrentCandleIdentityResetReason.ROLL_OVER_INCONSISTENT
        width_drift = abs(current.roi_width - previous.roi_width) / previous.roi_width
        height_drift = (
            abs(current.roi_height - previous.roi_height) / previous.roi_height
        )
        if max(width_drift, height_drift) > (
            self._config.maximum_roi_dimension_drift_ratio
        ):
            return CurrentCandleIdentityResetReason.ROI_CHANGED
        previous_pitch = previous.estimated_pitch_px
        current_pitch = current.estimated_pitch_px
        if previous_pitch is None or current_pitch is None:
            return CurrentCandleIdentityResetReason.MEMBERSHIP_UNAVAILABLE
        if not pitches_are_compatible(
            previous_pitch,
            current_pitch,
            maximum_relative_drift=self._config.maximum_pitch_drift_ratio,
        ):
            return CurrentCandleIdentityResetReason.PITCH_DISCONTINUITY
        return None

    @staticmethod
    def _ordering_problem(
        previous: CurrentCandleFrameContext | None,
        current: CurrentCandleFrameContext,
    ) -> CurrentCandleIdentityResetReason | None:
        if previous is None:
            return None
        if current.frame_id <= previous.frame_id:
            return CurrentCandleIdentityResetReason.FRAME_OUT_OF_ORDER
        if current.monotonic_timestamp <= previous.monotonic_timestamp:
            return CurrentCandleIdentityResetReason.TIME_REGRESSION
        if current.wall_timestamp < previous.wall_timestamp:
            return CurrentCandleIdentityResetReason.TIME_REGRESSION
        return None

    @staticmethod
    def _membership_available(context: CurrentCandleFrameContext) -> bool:
        membership = context.membership
        return (
            membership is not None
            and membership.status is CandleSeriesMembershipStatus.AVAILABLE
            and membership.estimated_pitch_px is not None
            and bool(context.member_candles)
        )

    @staticmethod
    def _append_frame_id(frame_ids: tuple[int, ...], frame_id: int) -> tuple[int, ...]:
        if frame_id in frame_ids:
            return frame_ids
        return (*frame_ids, frame_id)

    @staticmethod
    def _fresh_state(
        *,
        generation: int,
        active: bool,
        source_key: str | None = None,
        session_key: str | None = None,
        reset_reason: CurrentCandleIdentityResetReason | None = None,
    ) -> _ResolverState:
        return _ResolverState(
            lifecycle=CurrentCandleIdentityLifecycle.BOOTSTRAPPING,
            continuity_generation=generation,
            active=active,
            source_key=source_key,
            session_key=session_key,
            last_reset_reason=reset_reason,
        )

    def _fail_soft(
        self,
        state: _ResolverState,
        context: CurrentCandleFrameContext,
        error: Exception,
    ) -> tuple[_ResolverState, CurrentCandleIdentityResolution]:
        reset_state = self._fresh_state(
            generation=state.continuity_generation + 1,
            active=True,
            source_key=context.source_key,
            session_key=context.session_key,
            reset_reason=CurrentCandleIdentityResetReason.INTERNAL_ERROR,
        )
        diagnostic = f"internal_error:{type(error).__name__}"
        return reset_state, self._unavailable_resolution(
            context=context,
            state=reset_state,
            diagnostic=diagnostic,
            reset_reason=CurrentCandleIdentityResetReason.INTERNAL_ERROR,
        )
