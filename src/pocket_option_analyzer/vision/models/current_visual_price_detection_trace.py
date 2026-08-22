from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from .current_visual_price_extraction import (
    CurrentVisualPriceExtraction,
    CurrentVisualPriceStatus,
)


class CurrentVisualPriceRowRejectionReason(StrEnum):
    """Razón estructurada por la que una fila no representa el marcador."""

    LINE_RUN_TOO_SHORT = "line_run_too_short"
    LINE_CONTINUITY_TOO_LOW = "line_continuity_too_low"
    LINE_STARTS_TOO_LATE = "line_starts_too_late"
    LABEL_SUPPORT_MISSING = "label_support_missing"


@dataclass(frozen=True, slots=True)
class CurrentVisualPriceLabelSupportTrace:
    """Evidencia geométrica de etiqueta cercana a una fila de línea."""

    window_start_y: int
    window_end_y: int
    zone_start_x: int
    zone_end_x: int
    support_pixels: int
    support_row_count: int
    evaluated_row_count: int
    support_row_ratio: float
    support_density: float
    supported: bool
    diagnostic: str

    def __post_init__(self) -> None:
        if (
            min(
                self.window_start_y,
                self.zone_start_x,
                self.support_pixels,
                self.support_row_count,
                self.evaluated_row_count,
            )
            < 0
        ):
            raise ValueError("Las métricas de soporte no pueden ser negativas.")
        if self.window_end_y <= self.window_start_y:
            raise ValueError("La ventana vertical de soporte debe tener altura.")
        if self.zone_end_x <= self.zone_start_x:
            raise ValueError("La zona horizontal de soporte debe tener ancho.")
        if self.support_row_count > self.evaluated_row_count:
            raise ValueError("support_row_count excede evaluated_row_count.")
        if not all(
            isfinite(value) for value in (self.support_row_ratio, self.support_density)
        ):
            raise ValueError("Los ratios de soporte deben ser finitos.")
        if not 0.0 <= self.support_row_ratio <= 1.0:
            raise ValueError("support_row_ratio debe estar entre 0 y 1.")
        if not 0.0 <= self.support_density <= 1.0:
            raise ValueError("support_density debe estar entre 0 y 1.")
        if not self.diagnostic:
            raise ValueError("diagnostic no puede estar vacío.")


@dataclass(frozen=True, slots=True)
class CurrentVisualPriceRowEvaluationTrace:
    """Decisión auditable para una fila con máscara en la banda derecha."""

    row_y: int
    masked_pixels: int
    coverage: float
    span: float
    left_x: int
    right_x: int
    right_edge_gap: int
    longest_run_pixels: int
    longest_run_ratio: float
    longest_run_start_x: int
    longest_run_end_x: int
    component_count: int
    line_run_pixels: int
    line_run_span_pixels: int
    line_run_span_ratio: float
    line_run_start_x: int
    line_run_end_x: int
    line_run_continuity: float
    pass_coverage: bool
    pass_span: bool
    pass_edge: bool
    line_evidence: bool
    label_support: bool
    qualified: bool
    rejection_reasons: tuple[CurrentVisualPriceRowRejectionReason, ...]
    label_support_trace: CurrentVisualPriceLabelSupportTrace | None = None

    def __post_init__(self) -> None:
        integers = (
            self.row_y,
            self.masked_pixels,
            self.left_x,
            self.right_x,
            self.right_edge_gap,
            self.longest_run_pixels,
            self.longest_run_start_x,
            self.longest_run_end_x,
            self.component_count,
            self.line_run_pixels,
            self.line_run_span_pixels,
            self.line_run_start_x,
            self.line_run_end_x,
        )
        if any(value < 0 for value in integers):
            raise ValueError("Las métricas de fila no pueden ser negativas.")
        if self.masked_pixels == 0 or self.component_count == 0:
            raise ValueError("Una evaluación de fila debe contener máscara.")
        if self.left_x > self.right_x:
            raise ValueError("El rango horizontal de la fila es inválido.")
        if self.longest_run_start_x > self.longest_run_end_x:
            raise ValueError("El run continuo más largo es inválido.")
        if (
            self.longest_run_end_x - self.longest_run_start_x + 1
            != self.longest_run_pixels
        ):
            raise ValueError("La longitud del run continuo es inconsistente.")
        if self.line_run_start_x > self.line_run_end_x:
            raise ValueError("El run de evidencia de línea es inválido.")
        if self.line_run_end_x - self.line_run_start_x + 1 != self.line_run_span_pixels:
            raise ValueError("El span del run de línea es inconsistente.")
        if self.line_run_pixels > self.line_run_span_pixels:
            raise ValueError("line_run_pixels excede line_run_span_pixels.")
        ratios = (
            self.coverage,
            self.span,
            self.longest_run_ratio,
            self.line_run_span_ratio,
            self.line_run_continuity,
        )
        if not all(isfinite(value) and 0.0 <= value <= 1.0 for value in ratios):
            raise ValueError("Los ratios de fila deben estar entre 0 y 1.")
        if self.qualified != (self.line_evidence and self.label_support):
            raise ValueError("qualified debe reflejar línea y soporte de etiqueta.")
        if self.line_evidence != (self.label_support_trace is not None):
            raise ValueError("Solo las filas de línea deben incluir traza de etiqueta.")
        if self.label_support_trace is not None and (
            self.label_support != self.label_support_trace.supported
        ):
            raise ValueError("La decisión de etiqueta es inconsistente.")
        if self.qualified and self.rejection_reasons:
            raise ValueError("Una fila calificada no puede tener rechazos.")
        if not self.qualified and not self.rejection_reasons:
            raise ValueError("Una fila rechazada debe explicar su causa.")


@dataclass(frozen=True, slots=True)
class CurrentVisualPriceCandidateTrace:
    """Metadata de un candidato interno del extractor de precio visual."""

    candidate_id: str
    x: float
    y: float
    row_start: int
    row_end: int
    coverage: float
    span: float
    right_edge_gap: int
    score: float
    selected: bool

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError("candidate_id no puede estar vacío.")
        if not all(
            isfinite(value)
            for value in (self.x, self.y, self.coverage, self.span, self.score)
        ):
            raise ValueError("Las métricas del candidato deben ser finitas.")
        if self.row_start < 0 or self.row_end < self.row_start:
            raise ValueError("El rango de filas del candidato es inválido.")
        if self.right_edge_gap < 0:
            raise ValueError("right_edge_gap no puede ser negativo.")
        if not 0.0 <= self.coverage <= 1.0:
            raise ValueError("coverage debe estar entre 0 y 1.")
        if not 0.0 <= self.span <= 1.0:
            raise ValueError("span debe estar entre 0 y 1.")
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("score debe estar entre 0 y 1.")


@dataclass(frozen=True, slots=True)
class CurrentVisualPriceRejectionCounts:
    """Conteos observados durante los criterios existentes de búsqueda.

    Una misma fila puede incumplir más de un criterio; por eso los conteos
    de coverage, span y right-edge gap no son mutuamente excluyentes.
    """

    rows_without_mask_pixels: int = 0
    rows_with_mask_pixels: int = 0
    rejected_by_coverage: int = 0
    rejected_by_span: int = 0
    rejected_by_right_edge_gap: int = 0
    qualifying_rows: int = 0
    candidate_groups: int = 0
    rejected_by_group_height: int = 0
    line_evidence_rows: int = 0
    rejected_by_label_support: int = 0

    def __post_init__(self) -> None:
        counts = (
            self.rows_without_mask_pixels,
            self.rows_with_mask_pixels,
            self.rejected_by_coverage,
            self.rejected_by_span,
            self.rejected_by_right_edge_gap,
            self.qualifying_rows,
            self.candidate_groups,
            self.rejected_by_group_height,
            self.line_evidence_rows,
            self.rejected_by_label_support,
        )
        if any(value < 0 for value in counts):
            raise ValueError("Los conteos de rechazo no pueden ser negativos.")


@dataclass(frozen=True, slots=True)
class CurrentVisualPriceDetectionTrace:
    """Evidencia en memoria de una pasada del extractor de precio visual."""

    status: CurrentVisualPriceStatus
    image_width: int | None
    image_height: int | None
    effective_chart_right_x: int | None
    effective_chart_right_source: str | None
    band_start: int | None
    band_end: int | None
    band_width: int | None
    safe_top: int | None
    safe_bottom: int | None
    masked_pixel_count: int
    candidates: tuple[CurrentVisualPriceCandidateTrace, ...]
    rejection_counts: CurrentVisualPriceRejectionCounts
    row_evaluations: tuple[CurrentVisualPriceRowEvaluationTrace, ...] = ()
    decision_diagnostic: str | None = None

    def __post_init__(self) -> None:
        optional_dimensions = (
            self.image_width,
            self.image_height,
            self.effective_chart_right_x,
            self.band_start,
            self.band_end,
            self.band_width,
            self.safe_top,
            self.safe_bottom,
        )
        if any(value is not None and value < 0 for value in optional_dimensions):
            raise ValueError("Las dimensiones diagnósticas no pueden ser negativas.")
        if self.masked_pixel_count < 0:
            raise ValueError("masked_pixel_count no puede ser negativo.")
        row_ids = tuple(row.row_y for row in self.row_evaluations)
        if len(row_ids) != len(set(row_ids)):
            raise ValueError(
                "Las evaluaciones de fila deben tener coordenadas y únicas."
            )
        candidate_ids = tuple(candidate.candidate_id for candidate in self.candidates)
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("Los IDs de candidatos deben ser únicos por extracción.")
        selected_count = sum(candidate.selected for candidate in self.candidates)
        if selected_count > 1:
            raise ValueError("Como máximo un candidato puede estar seleccionado.")
        if self.candidates and selected_count != 1:
            raise ValueError(
                "Una traza con candidatos debe identificar el seleccionado."
            )
        if self.image_width is not None and self.effective_chart_right_x is not None:
            if self.effective_chart_right_x > self.image_width:
                raise ValueError("effective_chart_right_x excede image_width.")
        band_start = self.band_start
        band_end = self.band_end
        band_width = self.band_width
        if band_start is not None and band_end is not None and band_width is not None:
            if band_end - band_start != band_width:
                raise ValueError("La geometría de la banda es inconsistente.")
        counts = self.rejection_counts
        if self.image_height is not None and (
            counts.rows_without_mask_pixels + counts.rows_with_mask_pixels
            != self.image_height
        ):
            raise ValueError("Los conteos de filas no cubren image_height.")
        if counts.candidate_groups - counts.rejected_by_group_height != len(
            self.candidates
        ):
            raise ValueError("Los conteos de grupos no coinciden con candidates.")
        if self.row_evaluations and (
            len(self.row_evaluations) != counts.rows_with_mask_pixels
        ):
            raise ValueError("row_evaluations debe cubrir las filas con máscara.")
        if self.row_evaluations and (
            counts.line_evidence_rows < counts.qualifying_rows
        ):
            raise ValueError("qualifying_rows excede las filas de línea.")
        if self.row_evaluations and (
            counts.rejected_by_label_support > counts.line_evidence_rows
        ):
            raise ValueError("Los rechazos de etiqueta exceden las filas de línea.")


@dataclass(frozen=True, slots=True)
class CurrentVisualPriceAnalysis:
    """Extracción funcional y traza producidas por la misma ejecución."""

    extraction: CurrentVisualPriceExtraction
    trace: CurrentVisualPriceDetectionTrace

    def __post_init__(self) -> None:
        if self.extraction.status is not self.trace.status:
            raise ValueError("La extracción y su traza deben compartir status.")
        if self.extraction.candidate_count != len(self.trace.candidates):
            raise ValueError("candidate_count debe coincidir con la traza.")
        selected = tuple(
            candidate for candidate in self.trace.candidates if candidate.selected
        )
        if selected:
            candidate = selected[0]
            if (
                self.extraction.selected_x != candidate.x
                or self.extraction.selected_y != candidate.y
                or self.extraction.confidence != candidate.score
            ):
                raise ValueError(
                    "El candidato seleccionado debe coincidir con la extracción."
                )
