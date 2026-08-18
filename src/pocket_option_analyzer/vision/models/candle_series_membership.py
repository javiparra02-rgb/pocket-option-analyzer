from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from .classified_candle import ClassifiedCandle


class CandleSeriesMembershipStatus(StrEnum):
    """Disponibilidad de una hipótesis única de serie temporal."""

    AVAILABLE = "available"
    AMBIGUOUS = "ambiguous"
    INSUFFICIENT_SUPPORT = "insufficient_support"


class CandleSeriesMembershipExclusionReason(StrEnum):
    """Motivo estructural principal para no incluir un candidato."""

    HORIZONTAL_OUTLIER = "horizontal_outlier"
    VERTICAL_DISCONTINUITY = "vertical_discontinuity"
    NOT_SELECTED_CLUSTER = "not_selected_cluster"


@dataclass(frozen=True, slots=True)
class CandleSeriesMembershipExclusion:
    """Exclusión auditable de un candidato geométricamente válido."""

    candidate_id: str
    reason: CandleSeriesMembershipExclusionReason
    horizontal_gap_px: float | None = None
    vertical_gap_px: float | None = None
    diagnostic: str = ""

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError("candidate_id no puede estar vacío.")
        for value in (self.horizontal_gap_px, self.vertical_gap_px):
            if value is not None and (not isfinite(value) or value < 0):
                raise ValueError("Los gaps deben ser finitos y no negativos.")
        if not self.diagnostic:
            raise ValueError("diagnostic no puede estar vacío.")


@dataclass(frozen=True, slots=True)
class CandleSeriesMembershipGapTrace:
    """Evaluación relativa entre dos candidatos horizontalmente vecinos."""

    left_candidate_id: str
    right_candidate_id: str
    horizontal_gap_px: float
    estimated_slot_count: int | None
    horizontal_consistent: bool
    vertical_gap_px: float | None = None
    vertical_continuity_limit_px: float | None = None
    vertical_consistent: bool | None = None

    def __post_init__(self) -> None:
        if not self.left_candidate_id or not self.right_candidate_id:
            raise ValueError("Los IDs del gap no pueden estar vacíos.")
        if self.left_candidate_id == self.right_candidate_id:
            raise ValueError("Un gap requiere dos candidatos distintos.")
        if not isfinite(self.horizontal_gap_px) or self.horizontal_gap_px < 0:
            raise ValueError("horizontal_gap_px debe ser finito y no negativo.")
        if self.estimated_slot_count is not None and self.estimated_slot_count < 1:
            raise ValueError("estimated_slot_count debe ser positivo.")
        if self.horizontal_consistent and self.estimated_slot_count is None:
            raise ValueError(
                "Un gap horizontal consistente requiere un slot estimado."
            )
        for value in (self.vertical_gap_px, self.vertical_continuity_limit_px):
            if value is not None and (not isfinite(value) or value < 0):
                raise ValueError("La evidencia vertical debe ser finita y no negativa.")
        if self.vertical_consistent is not None and (
            self.vertical_gap_px is None
            or self.vertical_continuity_limit_px is None
        ):
            raise ValueError(
                "vertical_consistent requiere gap y límite vertical observables."
            )


@dataclass(frozen=True, slots=True)
class CandleSeriesMembershipRunTrace:
    """Hipótesis contigua producida por el consenso horizontal y vertical."""

    run_id: str
    candidate_ids: tuple[str, ...]
    selected: bool
    separated_by_vertical_discontinuity: bool = False

    def __post_init__(self) -> None:
        if not self.run_id:
            raise ValueError("run_id no puede estar vacío.")
        if not self.candidate_ids or any(not value for value in self.candidate_ids):
            raise ValueError("Un run debe contener IDs no vacíos.")
        if len(self.candidate_ids) != len(set(self.candidate_ids)):
            raise ValueError("Los IDs de un run no pueden repetirse.")

    @property
    def support(self) -> int:
        """Número de candidatos respaldados por el run."""

        return len(self.candidate_ids)


@dataclass(frozen=True, slots=True)
class CandleSeriesMembershipTrace:
    """Evidencia completa de una resolución aislada de pertenencia."""

    status: CandleSeriesMembershipStatus
    evaluated_candidate_ids: tuple[str, ...]
    member_candidate_ids: tuple[str, ...]
    excluded_candidates: tuple[CandleSeriesMembershipExclusion, ...]
    evaluated_gaps: tuple[CandleSeriesMembershipGapTrace, ...]
    estimated_pitch_px: float | None
    candidate_runs: tuple[CandleSeriesMembershipRunTrace, ...]
    selected_run_support: int
    latest_candidate_id: str | None
    diagnostic: str

    def __post_init__(self) -> None:
        evaluated_ids = self.evaluated_candidate_ids
        member_ids = self.member_candidate_ids
        excluded_ids = tuple(item.candidate_id for item in self.excluded_candidates)
        if any(not value for value in evaluated_ids):
            raise ValueError("Los IDs evaluados no pueden estar vacíos.")
        if len(evaluated_ids) != len(set(evaluated_ids)):
            raise ValueError("Los IDs evaluados no pueden repetirse.")
        if len(member_ids) != len(set(member_ids)):
            raise ValueError("Los IDs miembros no pueden repetirse.")
        if len(excluded_ids) != len(set(excluded_ids)):
            raise ValueError("Los IDs excluidos no pueden repetirse.")
        if set(member_ids) | set(excluded_ids) != set(evaluated_ids):
            raise ValueError("Miembros y exclusiones deben cubrir los evaluados.")
        if set(member_ids) & set(excluded_ids):
            raise ValueError("Un candidato no puede ser miembro y excluido.")
        if self.estimated_pitch_px is not None and (
            not isfinite(self.estimated_pitch_px) or self.estimated_pitch_px <= 0
        ):
            raise ValueError("estimated_pitch_px debe ser finito y positivo.")
        if self.selected_run_support < 0:
            raise ValueError("selected_run_support no puede ser negativo.")
        if not self.diagnostic:
            raise ValueError("diagnostic no puede estar vacío.")

        run_ids = tuple(run.run_id for run in self.candidate_runs)
        if len(run_ids) != len(set(run_ids)):
            raise ValueError("Los IDs de runs no pueden repetirse.")
        run_candidate_ids = tuple(
            candidate_id
            for run in self.candidate_runs
            for candidate_id in run.candidate_ids
        )
        if len(run_candidate_ids) != len(set(run_candidate_ids)):
            raise ValueError("Los runs deben ser disjuntos.")
        if set(run_candidate_ids) != set(evaluated_ids):
            raise ValueError("Los runs deben cubrir todos los candidatos evaluados.")

        selected_runs = tuple(run for run in self.candidate_runs if run.selected)
        if self.status is CandleSeriesMembershipStatus.AVAILABLE:
            if len(selected_runs) != 1:
                raise ValueError("AVAILABLE requiere exactamente un run seleccionado.")
            if selected_runs[0].candidate_ids != member_ids:
                raise ValueError("El run seleccionado debe coincidir con los miembros.")
            if self.selected_run_support != len(member_ids):
                raise ValueError("El soporte seleccionado debe coincidir con miembros.")
            if self.latest_candidate_id != member_ids[-1]:
                raise ValueError("latest_candidate_id debe ser el último miembro.")
        elif member_ids or selected_runs or self.selected_run_support != 0:
            raise ValueError("Un resultado no disponible no puede inventar miembros.")
        elif self.latest_candidate_id is not None:
            raise ValueError("Un resultado no disponible no puede tener latest.")


@dataclass(frozen=True, slots=True)
class CandleSeriesMembershipResult:
    """Miembros resueltos y su evidencia, sin construir CandleSeries."""

    candles: tuple[ClassifiedCandle, ...]
    candidate_ids: tuple[str, ...]
    trace: CandleSeriesMembershipTrace

    def __post_init__(self) -> None:
        if len(self.candles) != len(self.candidate_ids):
            raise ValueError("candles y candidate_ids deben estar alineados.")
        if self.candidate_ids != self.trace.member_candidate_ids:
            raise ValueError("Los IDs del resultado deben coincidir con la trace.")
        if (
            self.trace.status is not CandleSeriesMembershipStatus.AVAILABLE
            and (self.candles or self.candidate_ids)
        ):
            raise ValueError(
                "Un resultado no disponible debe devolver miembros vacíos."
            )
