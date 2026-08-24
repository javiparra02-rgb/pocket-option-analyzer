from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from math import isclose, isfinite

from pocket_option_analyzer.vision.models.candle_detection_trace import (
    FinalCandleTrace,
)
from pocket_option_analyzer.vision.models.candle_overlay_evidence import (
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
class CurrentCandleIdentityTrace:
    """Rich non-persisted diagnostic trace for later b15b2 stages."""

    frame_id: int
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
    diagnostics: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.frame_id < 0 or self.continuity_generation < 1:
            raise ValueError("Frame y generación deben ser válidos.")
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
