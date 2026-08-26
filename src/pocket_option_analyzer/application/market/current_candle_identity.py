from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from math import isclose, isfinite

from pocket_option_analyzer.vision.models.candle_detection_trace import (
    FinalCandleTrace,
)
from pocket_option_analyzer.vision.models.candle_overlay_evidence import (
    CandleOverlayEvidenceStatus,
    CandleOverlayEvidenceTrace,
)
from pocket_option_analyzer.vision.models.candle_series_membership import (
    CandleSeriesMembershipStatus,
    CandleSeriesMembershipTrace,
)


class CurrentCandleIdentityStatus(StrEnum):
    """Public shadow conclusion about the current candle identity."""

    CONFIRMED = "confirmed"
    MISSING_FROM_VIEW = "missing_from_view"
    UNAVAILABLE = "unavailable"
    AMBIGUOUS = "ambiguous"


class CurrentCandleIdentitySource(StrEnum):
    """Evidence path that produced a public identity conclusion."""

    NONE = "none"
    BOOTSTRAP_CONFIRMATION = "bootstrap_confirmation"
    STABLE_TRACKING = "stable_tracking"
    TRUSTED_ROLLOVER = "trusted_rollover"
    TERMINAL_SLOT_EMPTY = "terminal_slot_empty"


class CurrentCandleIdentityLifecycle(StrEnum):
    """Internal lifecycle exposed only as diagnostic shadow telemetry."""

    BOOTSTRAPPING = "bootstrapping"
    TRACKING = "tracking"
    DEGRADED = "degraded"


class CurrentCandleIdentityResetReason(StrEnum):
    """Explicit reasons for invalidating temporal identity state."""

    SESSION_STARTED = "session_started"
    SESSION_STOPPED = "session_stopped"
    SOURCE_CHANGED = "source_changed"
    FRAME_OUT_OF_ORDER = "frame_out_of_order"
    TIME_REGRESSION = "time_regression"
    ROI_CHANGED = "roi_changed"
    PITCH_DISCONTINUITY = "pitch_discontinuity"
    TRANSLATION_DISCONTINUITY = "translation_discontinuity"
    MEMBERSHIP_UNAVAILABLE = "membership_unavailable"
    ROLL_OVER_INCONSISTENT = "roll_over_inconsistent"
    EXPLICIT_RESET = "explicit_reset"
    INTERNAL_ERROR = "internal_error"


class CurrentCandleTranslationHypothesis(StrEnum):
    """Expected horizontal motion between two ordered candle sequences."""

    STABLE = "stable"
    ROLLOVER = "rollover"


class CurrentCandleMatchStatus(StrEnum):
    """Availability of a unique cross-frame translation hypothesis."""

    SELECTED = "selected"
    UNAVAILABLE = "unavailable"
    AMBIGUOUS = "ambiguous"


class TemporalRolloverEvaluationStatus(StrEnum):
    """Outcome of the resolver-owned temporal rollover trust evaluation."""

    NOT_EVALUATED = "not_evaluated"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class TemporalRolloverRejectionReason(StrEnum):
    """Deterministic gate that prevented temporal rollover trust."""

    NOT_EVALUATED = "not_evaluated"
    PREVIOUS_CONTEXT_UNAVAILABLE = "previous_context_unavailable"
    PREVIOUS_MEMBERSHIP_UNAVAILABLE = "previous_membership_unavailable"
    CURRENT_MEMBERSHIP_UNAVAILABLE = "current_membership_unavailable"
    MATCH_NOT_SELECTED = "match_not_selected"
    SELECTED_HYPOTHESIS_NOT_ROLLOVER = "selected_hypothesis_not_rollover"
    SUPPORT_BELOW_MINIMUM = "support_below_minimum"
    TYPE_RATIO_BELOW_MINIMUM = "type_ratio_below_minimum"
    RESIDUAL_UNAVAILABLE = "residual_unavailable"
    RESIDUAL_ABOVE_MAXIMUM = "residual_above_maximum"
    ROLLOVER_NOT_QUALIFIED = "rollover_not_qualified"
    PREVIOUS_BOUNDARY_INCOMPATIBLE = "previous_boundary_incompatible"
    CURRENT_BOUNDARY_INCOMPATIBLE = "current_boundary_incompatible"
    NO_BOUNDARY_CHANGE = "no_boundary_change"


class TerminalSeedEvaluationStatus(StrEnum):
    """Availability of positive terminal-current geometry for one rollover."""

    NOT_EVALUATED = "not_evaluated"
    OBSERVED = "observed"
    ABSENT = "absent"
    AMBIGUOUS = "ambiguous"
    OVERLAY = "overlay"
    INVALID_GEOMETRY = "invalid_geometry"


class TerminalSeedProvenance(StrEnum):
    """Only accepted provenance for a terminal seed in this shadow core."""

    NONE = "none"
    UNMATCHED_CURRENT_RIGHTMOST = "unmatched_current_rightmost"


class BootstrapConfirmationRejectionReason(StrEnum):
    """Reason a bootstrap frame did not establish confirmed tracking."""

    NOT_EVALUATED = "not_evaluated"
    TEMPORAL_ROLLOVER_REJECTED = "temporal_rollover_rejected"
    TERMINAL_SEED_ABSENT = "terminal_seed_absent"
    TERMINAL_SEED_INVALID = "terminal_seed_invalid"
    STABLE_NOT_SELECTED = "stable_not_selected"
    TERMINAL_CANDIDATE_NOT_UNIQUE = "terminal_candidate_not_unique"
    OVERLAY_CONFLICT = "overlay_conflict"


class TrackingTerminalDecisionReason(StrEnum):
    """Auditable reason for moving or preserving a confirmed terminal region."""

    NOT_EVALUATED = "not_evaluated"
    REGION_UPDATED_FROM_STABLE = "region_updated_from_stable"
    REGION_UPDATED_FROM_ROLLOVER_TERMINAL = (
        "region_updated_from_rollover_terminal"
    )
    REGION_PRESERVED_MATCH_AMBIGUOUS = "region_preserved_match_ambiguous"
    REGION_PRESERVED_MATCH_UNAVAILABLE = "region_preserved_match_unavailable"
    REGION_PRESERVED_MULTIPLE_CANDIDATES = (
        "region_preserved_multiple_candidates"
    )
    REGION_PRESERVED_COMPETITOR = "region_preserved_competitor"
    REGION_PRESERVED_OVERLAY = "region_preserved_overlay"
    REGION_PRESERVED_ROLLOVER_REJECTED = (
        "region_preserved_rollover_rejected"
    )
    REGION_PRESERVED_ROLLOVER_TERMINAL_ABSENT = (
        "region_preserved_rollover_terminal_absent"
    )
    REGION_PRESERVED_ROLLOVER_TERMINAL_OUTSIDE = (
        "region_preserved_rollover_terminal_outside"
    )
    REGION_PRESERVED_MISSING_FROM_VIEW = (
        "region_preserved_missing_from_view"
    )
    REGION_PRESERVED_MISSING_INSUFFICIENT = (
        "region_preserved_missing_insufficient"
    )


@dataclass(frozen=True, slots=True)
class CurrentCandleIdentityConfig:
    """Centralized provisional tolerances for the b15b2b1 shadow core.

    These defaults are deliberately conservative and remain calibration inputs
    for b15b2b5; none is a runtime trading threshold.
    """

    maximum_match_residual_pitch_ratio: float = 0.20
    minimum_historical_matches: int = 3
    minimum_type_match_ratio: float = 0.75
    hypothesis_type_ratio_margin: float = 0.15
    hypothesis_residual_margin_pitch_ratio: float = 0.05
    maximum_pitch_drift_ratio: float = 0.12
    maximum_roi_dimension_drift_ratio: float = 0.02
    terminal_region_half_width_pitch_ratio: float = 0.25
    terminal_region_width_margin_ratio: float = 0.50
    missing_previous_slot_tolerance_pitch_ratio: float = 0.30
    maximum_frame_id_step: int = 1

    def __post_init__(self) -> None:
        ratios = (
            self.maximum_match_residual_pitch_ratio,
            self.hypothesis_type_ratio_margin,
            self.hypothesis_residual_margin_pitch_ratio,
            self.maximum_pitch_drift_ratio,
            self.maximum_roi_dimension_drift_ratio,
            self.terminal_region_half_width_pitch_ratio,
            self.terminal_region_width_margin_ratio,
            self.missing_previous_slot_tolerance_pitch_ratio,
        )
        if any(not isfinite(value) or value < 0 for value in ratios):
            raise ValueError("Las tolerancias deben ser finitas y no negativas.")
        if not 0 <= self.minimum_type_match_ratio <= 1:
            raise ValueError("minimum_type_match_ratio debe estar entre 0 y 1.")
        if self.minimum_historical_matches < 1:
            raise ValueError("minimum_historical_matches debe ser positivo.")
        if self.maximum_frame_id_step < 1:
            raise ValueError("maximum_frame_id_step debe ser positivo.")


@dataclass(frozen=True, slots=True)
class TerminalSlotRegion:
    """Dynamically learned horizontal region for the mutable terminal slot."""

    center_x_roi: float
    lower_x_roi: float
    upper_x_roi: float
    normalized_center_x: float
    estimated_pitch_px: float
    continuity_generation: int
    learned_from_frame_ids: tuple[int, ...]

    def __post_init__(self) -> None:
        values = (
            self.center_x_roi,
            self.lower_x_roi,
            self.upper_x_roi,
            self.normalized_center_x,
            self.estimated_pitch_px,
        )
        if any(not isfinite(value) for value in values):
            raise ValueError("La región terminal requiere números finitos.")
        if not 0 <= self.lower_x_roi <= self.center_x_roi <= self.upper_x_roi:
            raise ValueError("La región terminal debe estar ordenada dentro del ROI.")
        if not 0 <= self.normalized_center_x <= 1:
            raise ValueError("normalized_center_x debe estar entre cero y uno.")
        if self.estimated_pitch_px <= 0:
            raise ValueError("estimated_pitch_px debe ser positivo.")
        if self.continuity_generation < 1:
            raise ValueError("continuity_generation debe ser positivo.")
        if len(self.learned_from_frame_ids) < 2:
            raise ValueError("La región debe conservar al menos dos frames origen.")
        if any(frame_id < 0 for frame_id in self.learned_from_frame_ids):
            raise ValueError("Los frame IDs no pueden ser negativos.")
        if len(self.learned_from_frame_ids) != len(
            set(self.learned_from_frame_ids)
        ):
            raise ValueError("Los frame IDs origen no pueden repetirse.")

    def contains(self, center_x_roi: float) -> bool:
        """Return whether a finite candidate center occupies the learned slot."""

        return (
            isfinite(center_x_roi)
            and self.lower_x_roi <= center_x_roi <= self.upper_x_roi
        )


@dataclass(frozen=True, slots=True)
class CurrentCandleIdentityEvidence:
    """Small structured proof attached to a semantic identity result."""

    matched_historical_member_count: int
    type_match_ratio: float
    terminal_candidate_ids: tuple[str, ...]
    sufficient: bool

    def __post_init__(self) -> None:
        if self.matched_historical_member_count < 0:
            raise ValueError("El soporte histórico no puede ser negativo.")
        if not isfinite(self.type_match_ratio) or not 0 <= self.type_match_ratio <= 1:
            raise ValueError("type_match_ratio debe estar entre cero y uno.")
        if any(not candidate_id for candidate_id in self.terminal_candidate_ids):
            raise ValueError("Los candidate IDs terminales no pueden estar vacíos.")
        if len(self.terminal_candidate_ids) != len(
            set(self.terminal_candidate_ids)
        ):
            raise ValueError("Los candidate IDs terminales no pueden repetirse.")


@dataclass(frozen=True, slots=True)
class CurrentCandleIdentityResult:
    """Small semantic result; rich diagnostics live in the companion trace."""

    status: CurrentCandleIdentityStatus
    candidate_id: str | None
    source: CurrentCandleIdentitySource
    terminal_region: TerminalSlotRegion | None
    estimated_pitch_px: float | None
    continuity_generation: int
    evidence: CurrentCandleIdentityEvidence | None
    diagnostics: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.continuity_generation < 1:
            raise ValueError("continuity_generation debe ser positivo.")
        if self.estimated_pitch_px is not None and (
            not isfinite(self.estimated_pitch_px) or self.estimated_pitch_px <= 0
        ):
            raise ValueError("estimated_pitch_px debe ser finito y positivo.")
        if not self.diagnostics or any(not value for value in self.diagnostics):
            raise ValueError("diagnostics debe contener mensajes estructurados.")
        asserts_candidate = self.status is CurrentCandleIdentityStatus.CONFIRMED
        if asserts_candidate != (self.candidate_id is not None):
            raise ValueError("Solo CONFIRMED puede afirmar candidate_id.")
        if self.candidate_id is not None and not self.candidate_id:
            raise ValueError("candidate_id no puede estar vacío.")
        if asserts_candidate:
            if self.terminal_region is None or self.estimated_pitch_px is None:
                raise ValueError("CONFIRMED requiere región y pitch válidos.")
            if self.evidence is None or not self.evidence.sufficient:
                raise ValueError("CONFIRMED requiere evidencia suficiente.")
            if self.candidate_id not in self.evidence.terminal_candidate_ids:
                raise ValueError("La evidencia debe contener el candidato confirmado.")
            if self.source not in (
                CurrentCandleIdentitySource.BOOTSTRAP_CONFIRMATION,
                CurrentCandleIdentitySource.STABLE_TRACKING,
                CurrentCandleIdentitySource.TRUSTED_ROLLOVER,
            ):
                raise ValueError("CONFIRMED requiere una fuente de tracking.")
        if self.status is CurrentCandleIdentityStatus.MISSING_FROM_VIEW:
            if self.terminal_region is None or self.estimated_pitch_px is None:
                raise ValueError("MISSING_FROM_VIEW requiere región y pitch.")
            if self.evidence is None or not self.evidence.sufficient:
                raise ValueError("MISSING_FROM_VIEW requiere evidencia suficiente.")
            if self.source is not CurrentCandleIdentitySource.TERMINAL_SLOT_EMPTY:
                raise ValueError("MISSING_FROM_VIEW requiere evidencia de slot vacío.")
        if self.status in (
            CurrentCandleIdentityStatus.UNAVAILABLE,
            CurrentCandleIdentityStatus.AMBIGUOUS,
        ) and self.source is not CurrentCandleIdentitySource.NONE:
            raise ValueError("Un resultado no concluyente no puede afirmar fuente.")


@dataclass(frozen=True, slots=True)
class CurrentCandleSequenceMatchMetrics:
    """Auditable metrics for one order-preserving translation hypothesis."""

    hypothesis: CurrentCandleTranslationHypothesis
    estimated_translation_px: float | None
    translation_in_pitch_units: float | None
    matched_member_count: int
    matched_historical_member_count: int
    matched_type_count: int
    type_match_ratio: float
    median_residual_px: float | None
    maximum_residual_px: float | None
    previous_candidate_ids: tuple[str, ...]
    current_candidate_ids: tuple[str, ...]
    unmatched_previous_candidate_ids: tuple[str, ...]
    unmatched_current_candidate_ids: tuple[str, ...]
    qualifies: bool

    def __post_init__(self) -> None:
        optional_values = (
            self.estimated_translation_px,
            self.translation_in_pitch_units,
            self.median_residual_px,
            self.maximum_residual_px,
        )
        if any(value is not None and not isfinite(value) for value in optional_values):
            raise ValueError("Las métricas opcionales deben ser finitas.")
        counts = (
            self.matched_member_count,
            self.matched_historical_member_count,
            self.matched_type_count,
        )
        if any(value < 0 for value in counts):
            raise ValueError("Los contadores de matching no pueden ser negativos.")
        if self.matched_historical_member_count > self.matched_member_count:
            raise ValueError("El soporte histórico no puede exceder el total.")
        if self.matched_type_count > self.matched_historical_member_count:
            raise ValueError("Los tipos coincidentes no pueden exceder la historia.")
        if not isfinite(self.type_match_ratio) or not 0 <= self.type_match_ratio <= 1:
            raise ValueError("type_match_ratio debe estar entre cero y uno.")
        if len(self.previous_candidate_ids) != self.matched_member_count:
            raise ValueError("Los IDs previos deben coincidir con el matching.")
        if len(self.current_candidate_ids) != self.matched_member_count:
            raise ValueError("Los IDs actuales deben coincidir con el matching.")
        if (self.matched_member_count == 0) != (
            self.estimated_translation_px is None
        ):
            raise ValueError("La translation existe exactamente cuando hay matches.")
        if (self.matched_member_count == 0) != (
            self.translation_in_pitch_units is None
        ):
            raise ValueError("La translation normalizada requiere matches.")
        if (self.matched_member_count == 0) != (
            self.median_residual_px is None
            and self.maximum_residual_px is None
        ):
            raise ValueError("Los residuals existen exactamente cuando hay matches.")


@dataclass(frozen=True, slots=True)
class CurrentCandleSequenceMatch:
    """Selection across stable and rollover translation hypotheses."""

    status: CurrentCandleMatchStatus
    selected_hypothesis: CurrentCandleTranslationHypothesis | None
    stable: CurrentCandleSequenceMatchMetrics
    rollover: CurrentCandleSequenceMatchMetrics
    diagnostics: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.stable.hypothesis is not CurrentCandleTranslationHypothesis.STABLE:
            raise ValueError("stable debe evaluar la hipótesis STABLE.")
        if self.rollover.hypothesis is not CurrentCandleTranslationHypothesis.ROLLOVER:
            raise ValueError("rollover debe evaluar la hipótesis ROLLOVER.")
        selected = self.status is CurrentCandleMatchStatus.SELECTED
        if selected != (self.selected_hypothesis is not None):
            raise ValueError("Solo SELECTED puede conservar una hipótesis elegida.")
        if selected and not self.selected_metrics.qualifies:
            raise ValueError("La hipótesis seleccionada debe ser calificable.")
        if not self.diagnostics or any(not value for value in self.diagnostics):
            raise ValueError("diagnostics no puede estar vacío.")

    @property
    def selected_metrics(self) -> CurrentCandleSequenceMatchMetrics:
        """Return selected metrics, rejecting access without a selection."""

        if self.selected_hypothesis is CurrentCandleTranslationHypothesis.STABLE:
            return self.stable
        if self.selected_hypothesis is CurrentCandleTranslationHypothesis.ROLLOVER:
            return self.rollover
        raise ValueError("No existe una hipótesis seleccionada.")


@dataclass(frozen=True, slots=True)
class CurrentCandleMissingEvidence:
    """Facts required before shadowing a missing terminal candle."""

    terminal_region_valid: bool
    terminal_member_absent: bool
    previous_slot_candidate_id: str | None
    previous_slot_fully_observable: bool
    previous_slot_distance_in_pitch_units: float | None
    candle_like_competitor_ids: tuple[str, ...]

    @property
    def sufficient(self) -> bool:
        """Whether all conservative missing-current conditions hold."""

        return (
            self.terminal_region_valid
            and self.terminal_member_absent
            and self.previous_slot_candidate_id is not None
            and self.previous_slot_fully_observable
            and self.previous_slot_distance_in_pitch_units is not None
            and not self.candle_like_competitor_ids
        )


@dataclass(frozen=True, slots=True)
class TrustedRolloverEvaluation:
    """Complete resolver-side proof for temporal rollover trust."""

    status: TemporalRolloverEvaluationStatus
    rejection_reason: TemporalRolloverRejectionReason | None
    match_status: CurrentCandleMatchStatus | None
    selected_hypothesis: CurrentCandleTranslationHypothesis | None
    rollover_qualifies: bool | None
    support_actual: int | None
    support_minimum: int | None
    support_pass: bool | None
    type_ratio_actual: float | None
    type_ratio_minimum: float | None
    type_ratio_pass: bool | None
    residual_actual_px: float | None
    residual_maximum_px: float | None
    residual_pass: bool | None
    previous_member_count: int | None
    current_member_count: int | None
    unmatched_previous_ids: tuple[str, ...]
    unmatched_current_ids: tuple[str, ...]
    expected_previous_leftmost_id: str | None
    expected_current_rightmost_id: str | None
    previous_boundary_compatible: bool | None
    current_boundary_compatible: bool | None
    temporal_rollover_trusted: bool

    @classmethod
    def not_evaluated(
        cls,
        reason: TemporalRolloverRejectionReason = (
            TemporalRolloverRejectionReason.NOT_EVALUATED
        ),
    ) -> TrustedRolloverEvaluation:
        """Return an explicit immutable absence of rollover evaluation."""

        return cls(
            status=TemporalRolloverEvaluationStatus.NOT_EVALUATED,
            rejection_reason=reason,
            match_status=None,
            selected_hypothesis=None,
            rollover_qualifies=None,
            support_actual=None,
            support_minimum=None,
            support_pass=None,
            type_ratio_actual=None,
            type_ratio_minimum=None,
            type_ratio_pass=None,
            residual_actual_px=None,
            residual_maximum_px=None,
            residual_pass=None,
            previous_member_count=None,
            current_member_count=None,
            unmatched_previous_ids=(),
            unmatched_current_ids=(),
            expected_previous_leftmost_id=None,
            expected_current_rightmost_id=None,
            previous_boundary_compatible=None,
            current_boundary_compatible=None,
            temporal_rollover_trusted=False,
        )

    def __post_init__(self) -> None:
        accepted = self.status is TemporalRolloverEvaluationStatus.ACCEPTED
        if accepted != self.temporal_rollover_trusted:
            raise ValueError("Only ACCEPTED can assert temporal rollover trust.")
        if accepted and self.rejection_reason is not None:
            raise ValueError("An accepted rollover cannot have a rejection reason.")
        if not accepted and self.rejection_reason is None:
            raise ValueError("A non-accepted rollover requires a reason.")
        counts = (
            self.support_actual,
            self.support_minimum,
            self.previous_member_count,
            self.current_member_count,
        )
        if any(value is not None and value < 0 for value in counts):
            raise ValueError("Rollover support and member counts cannot be negative.")
        ratios = (self.type_ratio_actual, self.type_ratio_minimum)
        if any(
            value is not None and (not isfinite(value) or not 0 <= value <= 1)
            for value in ratios
        ):
            raise ValueError("Rollover type ratios must be finite probabilities.")
        residuals = (self.residual_actual_px, self.residual_maximum_px)
        if any(
            value is not None and (not isfinite(value) or value < 0)
            for value in residuals
        ):
            raise ValueError("Rollover residuals must be finite and non-negative.")
        ids = (*self.unmatched_previous_ids, *self.unmatched_current_ids)
        if any(not candidate_id for candidate_id in ids):
            raise ValueError("Unmatched candidate IDs cannot be empty.")


@dataclass(frozen=True, slots=True)
class TerminalSeedEvaluation:
    """Positive, absent or rejected terminal-current evidence for a rollover."""

    status: TerminalSeedEvaluationStatus
    candidate_id: str | None
    provenance: TerminalSeedProvenance
    is_unmatched_current: bool | None
    is_current_rightmost: bool | None
    membership_included: bool | None
    geometry_valid: bool | None
    close_observable: bool | None
    overlay_status: CandleOverlayEvidenceStatus | None
    diagnostic: str

    @classmethod
    def not_evaluated(cls) -> TerminalSeedEvaluation:
        """Return an explicit immutable absence of terminal evaluation."""

        return cls(
            status=TerminalSeedEvaluationStatus.NOT_EVALUATED,
            candidate_id=None,
            provenance=TerminalSeedProvenance.NONE,
            is_unmatched_current=None,
            is_current_rightmost=None,
            membership_included=None,
            geometry_valid=None,
            close_observable=None,
            overlay_status=None,
            diagnostic="terminal_seed_not_evaluated",
        )

    def __post_init__(self) -> None:
        if not self.diagnostic:
            raise ValueError("Terminal seed diagnostics cannot be empty.")
        observed = self.status is TerminalSeedEvaluationStatus.OBSERVED
        if observed:
            if self.candidate_id is None:
                raise ValueError("An observed terminal seed requires a candidate.")
            if self.provenance is not (
                TerminalSeedProvenance.UNMATCHED_CURRENT_RIGHTMOST
            ):
                raise ValueError("Observed terminal provenance must be explicit.")
            if not all(
                value is True
                for value in (
                    self.is_unmatched_current,
                    self.is_current_rightmost,
                    self.membership_included,
                    self.geometry_valid,
                )
            ):
                raise ValueError("Observed terminal seed requires positive geometry.")
            if self.overlay_status is CandleOverlayEvidenceStatus.EXPIRY_OVERLAY:
                raise ValueError("An expiry overlay cannot be an observed terminal.")
        if self.candidate_id is not None and not self.candidate_id:
            raise ValueError("Terminal seed candidate_id cannot be empty.")


@dataclass(frozen=True, slots=True)
class BootstrapConfirmationEvaluation:
    """Before/after audit of the two-frame bootstrap confirmation contract."""

    evaluated: bool
    accepted: bool
    rejection_reason: BootstrapConfirmationRejectionReason | None
    pending_before: bool
    pending_after: bool
    lifecycle_before: CurrentCandleIdentityLifecycle | None
    lifecycle_after: CurrentCandleIdentityLifecycle | None
    selected_stable: bool | None
    provisional_region: TerminalSlotRegion | None
    candidates_in_region: tuple[str, ...]
    candidate_count: int
    overlay_conflict: bool
    resulting_status: CurrentCandleIdentityStatus | None

    @classmethod
    def not_evaluated(cls) -> BootstrapConfirmationEvaluation:
        """Return an explicit immutable absence of confirmation evaluation."""

        return cls(
            evaluated=False,
            accepted=False,
            rejection_reason=BootstrapConfirmationRejectionReason.NOT_EVALUATED,
            pending_before=False,
            pending_after=False,
            lifecycle_before=None,
            lifecycle_after=None,
            selected_stable=None,
            provisional_region=None,
            candidates_in_region=(),
            candidate_count=0,
            overlay_conflict=False,
            resulting_status=None,
        )

    def __post_init__(self) -> None:
        if self.candidate_count != len(self.candidates_in_region):
            raise ValueError("Bootstrap candidate count must match candidate IDs.")
        if self.accepted and (not self.evaluated or self.rejection_reason is not None):
            raise ValueError("Accepted bootstrap confirmation must be evaluated.")
        if self.evaluated and not self.accepted and self.rejection_reason is None:
            raise ValueError("Rejected bootstrap confirmation requires a reason.")


@dataclass(frozen=True, slots=True)
class TrackingTerminalEvaluation:
    """Region-preservation proof for one tracking or revalidation frame."""

    evaluated: bool
    region_before: TerminalSlotRegion | None
    region_after: TerminalSlotRegion | None
    selected_hypothesis: CurrentCandleTranslationHypothesis | None
    candidates_in_region: tuple[str, ...]
    rollover_terminal_status: TerminalSeedEvaluationStatus
    candidate_provenance: TerminalSeedProvenance
    competitor_ids: tuple[str, ...]
    overlay_conflict: bool
    missing_evidence: CurrentCandleMissingEvidence | None
    resulting_status: CurrentCandleIdentityStatus | None
    region_moved: bool
    decision_reason: TrackingTerminalDecisionReason

    @classmethod
    def not_evaluated(cls) -> TrackingTerminalEvaluation:
        """Return an explicit immutable absence of tracking evaluation."""

        return cls(
            evaluated=False,
            region_before=None,
            region_after=None,
            selected_hypothesis=None,
            candidates_in_region=(),
            rollover_terminal_status=TerminalSeedEvaluationStatus.NOT_EVALUATED,
            candidate_provenance=TerminalSeedProvenance.NONE,
            competitor_ids=(),
            overlay_conflict=False,
            missing_evidence=None,
            resulting_status=None,
            region_moved=False,
            decision_reason=TrackingTerminalDecisionReason.NOT_EVALUATED,
        )

    def __post_init__(self) -> None:
        if self.region_moved and (
            self.region_before is None or self.region_after is None
        ):
            raise ValueError("A moved region requires before and after geometry.")
        ids = (*self.candidates_in_region, *self.competitor_ids)
        if any(not candidate_id for candidate_id in ids):
            raise ValueError("Tracking candidate IDs cannot be empty.")


@dataclass(frozen=True, slots=True)
class CurrentCandleIdentityTrace:
    """Rich diagnostic trace persisted by the opt-in shadow evidence path."""

    frame_id: int
    wall_timestamp: datetime
    monotonic_timestamp: float
    source_key: str
    session_key: str
    status: CurrentCandleIdentityStatus
    internal_state: CurrentCandleIdentityLifecycle
    continuity_generation: int
    legacy_latest_candidate_id: str | None
    terminal_region: TerminalSlotRegion | None
    estimated_pitch_px: float | None
    sequence_match: CurrentCandleSequenceMatch | None
    rollover_suspected: bool
    rollover_confirmed: bool
    chosen_candidate_id: str | None
    missing_evidence: CurrentCandleMissingEvidence | None
    reset_reason: CurrentCandleIdentityResetReason | None
    expiry_evidence_consistent: bool | None
    expiry_vertical_line_x: int | None
    expiry_vertical_line_conflict: bool
    diagnostics: tuple[str, ...]
    expiry_vertical_line_start_y: int | None = None
    expiry_vertical_line_end_y: int | None = None
    trusted_rollover_evaluation: TrustedRolloverEvaluation = field(
        default_factory=TrustedRolloverEvaluation.not_evaluated
    )
    terminal_seed_evaluation: TerminalSeedEvaluation = field(
        default_factory=TerminalSeedEvaluation.not_evaluated
    )
    bootstrap_confirmation_evaluation: BootstrapConfirmationEvaluation = field(
        default_factory=BootstrapConfirmationEvaluation.not_evaluated
    )
    tracking_terminal_evaluation: TrackingTerminalEvaluation = field(
        default_factory=TrackingTerminalEvaluation.not_evaluated
    )

    def __post_init__(self) -> None:
        if self.frame_id < 0 or self.continuity_generation < 1:
            raise ValueError("Frame y generación deben ser válidos.")
        if not isinstance(self.wall_timestamp, datetime):
            raise TypeError("wall_timestamp debe ser datetime.")
        if not isfinite(self.monotonic_timestamp) or self.monotonic_timestamp < 0:
            raise ValueError("monotonic_timestamp debe ser finito y no negativo.")
        if not self.source_key or not self.session_key:
            raise ValueError("source_key y session_key no pueden estar vacíos.")
        if self.expiry_vertical_line_x is not None and (
            self.expiry_vertical_line_x < 0
        ):
            raise ValueError("expiry_vertical_line_x no puede ser negativo.")
        if self.expiry_vertical_line_conflict and (
            self.expiry_vertical_line_x is not None
        ):
            raise ValueError("Un conflicto expiry no puede elegir una X canónica.")
        line_coordinates = (
            self.expiry_vertical_line_x,
            self.expiry_vertical_line_start_y,
            self.expiry_vertical_line_end_y,
        )
        if any(value is not None for value in line_coordinates) and not all(
            value is not None for value in line_coordinates
        ):
            raise ValueError("La geometría expiry debe estar disponible completa.")
        if all(value is not None for value in line_coordinates):
            assert self.expiry_vertical_line_start_y is not None
            assert self.expiry_vertical_line_end_y is not None
            if min(value for value in line_coordinates if value is not None) < 0:
                raise ValueError("La geometría expiry no puede ser negativa.")
            if self.expiry_vertical_line_start_y > self.expiry_vertical_line_end_y:
                raise ValueError("La geometría expiry vertical debe estar ordenada.")
        if self.chosen_candidate_id is not None and not self.chosen_candidate_id:
            raise ValueError("chosen_candidate_id no puede estar vacío.")
        if self.rollover_confirmed and not self.rollover_suspected:
            raise ValueError("Un rollover confirmado debe haber sido sospechado.")
        if not self.diagnostics or any(not value for value in self.diagnostics):
            raise ValueError("diagnostics no puede estar vacío.")


@dataclass(frozen=True, slots=True)
class CurrentCandleIdentityResolution:
    """Atomic semantic result and its rich diagnostic trace."""

    result: CurrentCandleIdentityResult
    trace: CurrentCandleIdentityTrace

    def __post_init__(self) -> None:
        if self.result.status is not self.trace.status:
            raise ValueError("Result y trace deben compartir status.")
        if self.result.continuity_generation != self.trace.continuity_generation:
            raise ValueError("Result y trace deben compartir generation.")
        if self.result.candidate_id != self.trace.chosen_candidate_id:
            raise ValueError("Result y trace deben compartir candidate_id.")


@dataclass(frozen=True, slots=True)
class CurrentCandleFrameContext:
    """Pure input context for one isolated identity-resolution pass."""

    frame_id: int
    wall_timestamp: datetime
    monotonic_timestamp: float
    roi_width: int
    roi_height: int
    source_key: str
    session_key: str
    membership: CandleSeriesMembershipTrace | None
    final_candles: tuple[FinalCandleTrace, ...]
    overlay_evidence: CandleOverlayEvidenceTrace | None = None
    expiry_evidence_consistent: bool | None = None
    expiry_vertical_line_x: int | None = None
    expiry_vertical_line_conflict: bool = False
    expiry_vertical_line_start_y: int | None = None
    expiry_vertical_line_end_y: int | None = None

    def __post_init__(self) -> None:
        if self.frame_id < 0:
            raise ValueError("frame_id no puede ser negativo.")
        if not isinstance(self.wall_timestamp, datetime):
            raise TypeError("wall_timestamp debe ser datetime.")
        if not isfinite(self.monotonic_timestamp) or self.monotonic_timestamp < 0:
            raise ValueError("monotonic_timestamp debe ser finito y no negativo.")
        if self.roi_width < 1 or self.roi_height < 1:
            raise ValueError("Las dimensiones del ROI deben ser positivas.")
        if not self.source_key or not self.session_key:
            raise ValueError("source_key y session_key no pueden estar vacíos.")
        if self.expiry_vertical_line_x is not None and (
            self.expiry_vertical_line_x < 0
        ):
            raise ValueError("expiry_vertical_line_x no puede ser negativo.")
        if self.expiry_vertical_line_conflict and (
            self.expiry_vertical_line_x is not None
        ):
            raise ValueError("Un conflicto expiry no puede elegir una X canónica.")
        line_coordinates = (
            self.expiry_vertical_line_x,
            self.expiry_vertical_line_start_y,
            self.expiry_vertical_line_end_y,
        )
        if any(value is not None for value in line_coordinates) and not all(
            value is not None for value in line_coordinates
        ):
            raise ValueError("La geometría expiry debe estar disponible completa.")
        if all(value is not None for value in line_coordinates):
            assert self.expiry_vertical_line_start_y is not None
            assert self.expiry_vertical_line_end_y is not None
            if min(value for value in line_coordinates if value is not None) < 0:
                raise ValueError("La geometría expiry no puede ser negativa.")
            if self.expiry_vertical_line_start_y > self.expiry_vertical_line_end_y:
                raise ValueError("La geometría expiry vertical debe estar ordenada.")
        final_ids = tuple(candle.candidate_id for candle in self.final_candles)
        if len(final_ids) != len(set(final_ids)):
            raise ValueError("final_candles no puede repetir candidate_id.")
        if self.membership is not None:
            if not set(self.membership.evaluated_candidate_ids).issubset(final_ids):
                raise ValueError("Membership debe referirse a final_candles.")
        if self.overlay_evidence is not None and not set(
            self.overlay_evidence.evaluated_candidate_ids
        ).issubset(final_ids):
            raise ValueError("Overlay evidence debe referirse a final_candles.")

    @property
    def membership_status(self) -> CandleSeriesMembershipStatus | None:
        """Return the upstream membership status without inventing a fallback."""

        return self.membership.status if self.membership is not None else None

    @property
    def estimated_pitch_px(self) -> float | None:
        """Return the pitch supplied canonically by membership."""

        return self.membership.estimated_pitch_px if self.membership else None

    @property
    def member_candles(self) -> tuple[FinalCandleTrace, ...]:
        """Return AVAILABLE members in membership order, never raw fallback."""

        membership = self.membership
        if (
            membership is None
            or membership.status is not CandleSeriesMembershipStatus.AVAILABLE
        ):
            return ()
        by_id = {candle.candidate_id: candle for candle in self.final_candles}
        return tuple(
            by_id[candidate_id]
            for candidate_id in membership.member_candidate_ids
        )


def candle_center_x(candle: FinalCandleTrace) -> float:
    """Return a final candle's horizontal center in ROI coordinates."""

    return candle.x + candle.width / 2


def pitches_are_compatible(
    left: float,
    right: float,
    *,
    maximum_relative_drift: float,
) -> bool:
    """Compare two positive pitches using a symmetric relative drift."""

    if min(left, right) <= 0:
        return False
    return abs(left - right) / max(left, right) <= maximum_relative_drift or isclose(
        left,
        right,
    )
