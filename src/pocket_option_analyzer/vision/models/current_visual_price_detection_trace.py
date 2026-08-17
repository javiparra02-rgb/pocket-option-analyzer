from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from .current_visual_price_extraction import (
    CurrentVisualPriceExtraction,
    CurrentVisualPriceStatus,
)


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
