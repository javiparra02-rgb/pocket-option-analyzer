from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from .candle_candidate import CandleCandidate
from .candle_color import CandleColor
from .candle_geometry import CandleGeometry
from .candle_type import CandleType
from .classified_candle import ClassifiedCandle


class CandleCandidateDecision(StrEnum):
    """Decisiones cerradas que ya aplica el pipeline de detección."""

    SEGMENTED = "segmented"
    DIMENSION_ACCEPTED = "dimension_accepted"
    REJECTED_DIMENSION = "rejected_dimension"
    WIDTH_ACCEPTED = "width_accepted"
    REJECTED_WIDTH = "rejected_width"
    MERGED = "merged"
    MERGE_RESULT = "merge_result"
    TRUNCATED = "truncated"
    RETURNED = "returned"


class CandleDimensionRejectionReason(StrEnum):
    """Comparación dimensional existente que rechazó un candidato."""

    AREA_BELOW_MINIMUM = "area_below_minimum"
    WIDTH_BELOW_MINIMUM = "width_below_minimum"
    HEIGHT_BELOW_MINIMUM = "height_below_minimum"
    WIDTH_ABOVE_MAXIMUM = "width_above_maximum"
    HEIGHT_ABOVE_MAXIMUM = "height_above_maximum"


class CandleWidthDecisionReason(StrEnum):
    """Rama efectiva del criterio de ancho dominante."""

    WITHIN_DOMINANT_RANGE = "within_dominant_range"
    LEFT_EDGE_EXCEPTION = "left_edge_exception"
    OUTSIDE_DOMINANT_RANGE = "outside_dominant_range"


class CandleAnchorExclusionReason(StrEnum):
    """Motivo por el que una vela final no fue utilizada como anchor."""

    NOT_EVALUATED = "not_evaluated"
    LATEST = "latest"
    UNKNOWN_CANDLE_TYPE = "unknown_candle_type"
    MISSING_GEOMETRY = "missing_geometry"


@dataclass(frozen=True, slots=True)
class CandleCandidateTrace:
    """Lifecycle de un candidato segmentado o producido por un merge."""

    candidate_id: str
    x: int
    y: int
    width: int
    height: int
    area: int
    color: CandleColor
    decisions: tuple[CandleCandidateDecision, ...]
    dominant_width: float | None = None
    dimension_rejection_reasons: tuple[CandleDimensionRejectionReason, ...] = ()
    width_decision_reason: CandleWidthDecisionReason | None = None
    merged_from: tuple[str, ...] = ()
    merged_into: str | None = None

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError("candidate_id no puede estar vacío.")
        if any(
            value < 0 for value in (self.x, self.y, self.width, self.height, self.area)
        ):
            raise ValueError("La geometría diagnóstica no puede ser negativa.")
        if not self.decisions:
            raise ValueError("decisions debe conservar al menos una decisión.")
        if self.dominant_width is not None and (
            not isfinite(self.dominant_width) or self.dominant_width <= 0
        ):
            raise ValueError("dominant_width debe ser finito y positivo.")
        if CandleCandidateDecision.MERGE_RESULT in self.decisions:
            if not self.merged_from:
                raise ValueError("Un resultado de merge debe conservar su procedencia.")
        elif self.merged_from:
            raise ValueError("merged_from solo corresponde a resultados de merge.")
        if CandleCandidateDecision.MERGED in self.decisions:
            if self.merged_into is None:
                raise ValueError("Un candidato fusionado debe indicar merged_into.")
        elif self.merged_into is not None:
            raise ValueError("merged_into solo corresponde a candidatos fusionados.")
        is_dimension_rejected = (
            CandleCandidateDecision.REJECTED_DIMENSION in self.decisions
        )
        if is_dimension_rejected != bool(self.dimension_rejection_reasons):
            raise ValueError(
                "Los motivos dimensionales deben coincidir con la decisión."
            )
        has_width_decision = any(
            decision in self.decisions
            for decision in (
                CandleCandidateDecision.WIDTH_ACCEPTED,
                CandleCandidateDecision.REJECTED_WIDTH,
            )
        )
        if has_width_decision != (self.width_decision_reason is not None):
            raise ValueError("La decisión de ancho debe conservar su motivo.")


@dataclass(frozen=True, slots=True)
class CandleFilterConfigurationTrace:
    """Configuración efectiva que gobernó una pasada de CandleFilter."""

    min_area: int
    min_width: int
    min_height: int
    max_width: int
    max_height: int
    min_relative_width: float
    max_relative_width: float
    width_bucket_size: int
    anchor_min_height_ratio: float
    same_column_center_ratio: float
    max_candidates: int

    def __post_init__(self) -> None:
        if self.min_area < 1 or min(self.min_width, self.min_height) < 1:
            raise ValueError("Los mínimos efectivos deben ser positivos.")
        if self.max_width < self.min_width or self.max_height < self.min_height:
            raise ValueError("Los máximos efectivos no pueden ser menores.")
        ratios = (
            self.min_relative_width,
            self.max_relative_width,
            self.anchor_min_height_ratio,
            self.same_column_center_ratio,
        )
        if any(not isfinite(value) or value <= 0 for value in ratios):
            raise ValueError(
                "Las proporciones efectivas deben ser finitas y positivas."
            )
        if self.max_relative_width < self.min_relative_width:
            raise ValueError("El rango relativo efectivo es inválido.")
        if self.width_bucket_size < 1 or self.max_candidates < 1:
            raise ValueError("Los límites discretos efectivos deben ser positivos.")


@dataclass(frozen=True, slots=True)
class CandleMergeTrace:
    """Procedencia y umbral usados por una fusión ya efectuada."""

    result_candidate_id: str
    source_candidate_ids: tuple[str, ...]
    maximum_center_distance: float

    def __post_init__(self) -> None:
        if not self.result_candidate_id:
            raise ValueError("result_candidate_id no puede estar vacío.")
        if len(self.source_candidate_ids) < 2:
            raise ValueError("Un merge debe conservar al menos dos candidatos origen.")
        if any(not candidate_id for candidate_id in self.source_candidate_ids):
            raise ValueError("Los IDs origen de un merge no pueden estar vacíos.")
        if (
            not isfinite(self.maximum_center_distance)
            or self.maximum_center_distance < 0
        ):
            raise ValueError("maximum_center_distance debe ser finito y no negativo.")


@dataclass(frozen=True, slots=True)
class FinalCandleTrace:
    """Candle final clasificada y su rol en la referencia visual."""

    candidate_id: str
    source_candidate_ids: tuple[str, ...]
    ordinal: int
    x: int
    y: int
    width: int
    height: int
    area: int
    color: CandleColor
    candle_type: CandleType
    geometry: CandleGeometry | None
    is_latest: bool
    is_anchor: bool = False
    anchor_index: int | None = None
    anchor_exclusion_reason: CandleAnchorExclusionReason | None = (
        CandleAnchorExclusionReason.NOT_EVALUATED
    )

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError("candidate_id no puede estar vacío.")
        if not self.source_candidate_ids:
            raise ValueError("Una candle final debe conservar su procedencia.")
        if self.ordinal < 0:
            raise ValueError("ordinal no puede ser negativo.")
        if any(
            value < 0 for value in (self.x, self.y, self.width, self.height, self.area)
        ):
            raise ValueError("La geometría diagnóstica no puede ser negativa.")
        if self.is_latest and self.is_anchor:
            raise ValueError("Una candle no puede ser latest y anchor simultáneamente.")
        if self.is_anchor != (self.anchor_index is not None):
            raise ValueError("anchor_index debe existir exactamente para los anchors.")
        if self.anchor_index is not None and self.anchor_index < 0:
            raise ValueError("anchor_index no puede ser negativo.")
        if self.is_anchor and self.anchor_exclusion_reason is not None:
            raise ValueError("Un anchor no puede tener motivo de exclusión.")

    @property
    def high_y(self) -> int | None:
        return self.geometry.high_y if self.geometry is not None else None

    @property
    def body_top_y(self) -> int | None:
        return self.geometry.body_top_y if self.geometry is not None else None

    @property
    def body_bottom_y(self) -> int | None:
        return self.geometry.body_bottom_y if self.geometry is not None else None

    @property
    def low_y(self) -> int | None:
        return self.geometry.low_y if self.geometry is not None else None


@dataclass(frozen=True, slots=True)
class CandleDetectionTrace:
    """Evidencia estructurada completa de una pasada de detección."""

    candidates: tuple[CandleCandidateTrace, ...]
    merges: tuple[CandleMergeTrace, ...]
    returned_candidate_ids: tuple[str, ...]
    dominant_width: float | None
    maximum_returned_candidates: int
    filter_configuration: CandleFilterConfigurationTrace | None = None
    final_candles: tuple[FinalCandleTrace, ...] = ()

    def __post_init__(self) -> None:
        if self.maximum_returned_candidates < 1:
            raise ValueError("maximum_returned_candidates debe ser positivo.")
        candidate_ids = tuple(candidate.candidate_id for candidate in self.candidates)
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("Los IDs de candidatos deben ser únicos por frame.")
        known_ids = set(candidate_ids)
        if len(self.returned_candidate_ids) != len(set(self.returned_candidate_ids)):
            raise ValueError("Los IDs retornados no pueden repetirse.")
        if any(
            candidate_id not in known_ids
            for candidate_id in self.returned_candidate_ids
        ):
            raise ValueError(
                "Todos los candidatos retornados deben existir en la traza."
            )
        if len(self.returned_candidate_ids) > self.maximum_returned_candidates:
            raise ValueError("La traza excede el límite de candidatos retornados.")
        if self.dominant_width is not None and (
            not isfinite(self.dominant_width) or self.dominant_width <= 0
        ):
            raise ValueError("dominant_width debe ser finito y positivo.")
        if any(candle.candidate_id not in known_ids for candle in self.final_candles):
            raise ValueError(
                "Toda candle final debe proceder de un candidato conocido."
            )
        if any(
            source_id not in known_ids
            for candle in self.final_candles
            for source_id in candle.source_candidate_ids
        ):
            raise ValueError("Toda procedencia final debe existir en candidates.")
        if tuple(candle.ordinal for candle in self.final_candles) != tuple(
            range(len(self.final_candles))
        ):
            raise ValueError("Los ordinales finales deben ser consecutivos.")
        for merge in self.merges:
            if merge.result_candidate_id not in known_ids:
                raise ValueError("Todo resultado de merge debe existir en candidates.")
            if any(
                source_id not in known_ids for source_id in merge.source_candidate_ids
            ):
                raise ValueError("Todo origen de merge debe existir en candidates.")


@dataclass(frozen=True, slots=True)
class CandleFilterResult:
    """Resultado funcional y traza producidos por una sola pasada del filtro."""

    candidates: tuple[CandleCandidate, ...]
    candidate_ids: tuple[str, ...]
    trace: CandleDetectionTrace

    def __post_init__(self) -> None:
        if len(self.candidates) != len(self.candidate_ids):
            raise ValueError("candidates y candidate_ids deben estar alineados.")
        if self.candidate_ids != self.trace.returned_candidate_ids:
            raise ValueError("Los IDs retornados deben coincidir con la traza.")


@dataclass(frozen=True, slots=True)
class CandleDetectionResult:
    """Candidatos detectados y evidencia de la misma ejecución."""

    candidates: tuple[CandleCandidate, ...]
    candidate_ids: tuple[str, ...]
    trace: CandleDetectionTrace

    def __post_init__(self) -> None:
        if len(self.candidates) != len(self.candidate_ids):
            raise ValueError("candidates y candidate_ids deben estar alineados.")
        if self.candidate_ids != self.trace.returned_candidate_ids:
            raise ValueError("Los IDs detectados deben coincidir con la traza.")


@dataclass(frozen=True, slots=True)
class CandleAnalysisResult:
    """Velas clasificadas y evidencia de la misma ejecución."""

    candles: tuple[ClassifiedCandle, ...]
    candidate_ids: tuple[str, ...]
    trace: CandleDetectionTrace

    def __post_init__(self) -> None:
        if len(self.candles) != len(self.candidate_ids):
            raise ValueError("candles y candidate_ids deben estar alineados.")
        if self.candidate_ids != self.trace.returned_candidate_ids:
            raise ValueError("Los IDs clasificados deben coincidir con la traza.")
