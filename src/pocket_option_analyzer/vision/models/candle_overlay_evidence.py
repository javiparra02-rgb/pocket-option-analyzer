from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite


class CandleOverlayEvidenceStatus(StrEnum):
    """Resultado de buscar estructura visual propia del overlay de expiry."""

    EXPIRY_OVERLAY = "expiry_overlay"
    NO_EVIDENCE = "no_evidence"
    NOT_EVALUABLE = "not_evaluable"


@dataclass(frozen=True, slots=True)
class CandleOverlayEvidence:
    """Evidencia negativa asociada a un candidato determinístico."""

    candidate_id: str
    status: CandleOverlayEvidenceStatus
    vertical_line_support_ratio: float | None
    contact_gap_ratio: float | None
    horizontal_alignment_ratio: float | None
    cap_height_to_width_ratio: float
    wickless: bool | None
    diagnostic: str

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError("candidate_id no puede estar vacío.")
        if (
            not isfinite(self.cap_height_to_width_ratio)
            or self.cap_height_to_width_ratio <= 0
        ):
            raise ValueError(
                "cap_height_to_width_ratio debe ser finito y positivo."
            )
        if self.vertical_line_support_ratio is not None and (
            not isfinite(self.vertical_line_support_ratio)
            or not 0 <= self.vertical_line_support_ratio <= 1
        ):
            raise ValueError(
                "vertical_line_support_ratio debe estar entre cero y uno."
            )
        for value in (
            self.contact_gap_ratio,
            self.horizontal_alignment_ratio,
        ):
            if value is not None and (not isfinite(value) or value < 0):
                raise ValueError(
                    "Las relaciones geométricas deben ser finitas y no negativas."
                )
        if not self.diagnostic:
            raise ValueError("diagnostic no puede estar vacío.")
        metrics_available = self.vertical_line_support_ratio is not None
        if metrics_available != (
            self.contact_gap_ratio is not None
            and self.horizontal_alignment_ratio is not None
        ):
            raise ValueError(
                "Las métricas de línea deben estar disponibles conjuntamente."
            )
        if self.status is CandleOverlayEvidenceStatus.NOT_EVALUABLE:
            if metrics_available:
                raise ValueError(
                    "NOT_EVALUABLE no puede afirmar métricas de línea."
                )
        elif not metrics_available:
            raise ValueError(
                "Una evaluación completada debe conservar métricas de línea."
            )


@dataclass(frozen=True, slots=True)
class CandleOverlayEvidenceTrace:
    """Evidencia de overlay alineada con todos los candidatos evaluados."""

    evaluated_candidate_ids: tuple[str, ...]
    evidence: tuple[CandleOverlayEvidence, ...]

    def __post_init__(self) -> None:
        if any(not candidate_id for candidate_id in self.evaluated_candidate_ids):
            raise ValueError("Los IDs evaluados no pueden estar vacíos.")
        if len(self.evaluated_candidate_ids) != len(
            set(self.evaluated_candidate_ids)
        ):
            raise ValueError("Los IDs evaluados no pueden repetirse.")
        evidence_ids = tuple(item.candidate_id for item in self.evidence)
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("La evidencia no puede repetir candidate_id.")
        if evidence_ids != self.evaluated_candidate_ids:
            raise ValueError(
                "La evidencia debe estar exactamente alineada con los candidatos."
            )

    def by_candidate_id(self) -> dict[str, CandleOverlayEvidence]:
        """Devuelve una vista nueva indexada por el ID determinístico."""

        return {item.candidate_id: item for item in self.evidence}
