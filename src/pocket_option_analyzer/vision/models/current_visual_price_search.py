from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite


class CurrentVisualPriceSearchWindowOrigin(StrEnum):
    """Origen verificable de una ventana de búsqueda."""

    SEMANTIC_LINE_LABEL_PAIR = "semantic_line_label_pair"
    FIXED_OVERRIDE = "fixed_override"


class CurrentVisualPriceSearchPlanStatus(StrEnum):
    """Disponibilidad del plan antes de ejecutar el qualifier."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class CurrentVisualPriceSearchPlanReason(StrEnum):
    """Razón estructurada de la resolución de ventanas."""

    SEMANTIC_WINDOWS_AVAILABLE = "semantic_windows_available"
    FIXED_OVERRIDE = "fixed_override"
    NO_MASK_PIXELS = "no_mask_pixels"
    NO_HORIZONTAL_LINE_HYPOTHESES = "no_horizontal_line_hypotheses"
    NO_LABEL_COMPONENT_HYPOTHESES = "no_label_component_hypotheses"
    NO_COMPATIBLE_LINE_LABEL_PAIRS = "no_compatible_line_label_pairs"
    WINDOW_LIMIT_EXCEEDED = "window_limit_exceeded"


class CurrentVisualPriceSemanticSearchMode(StrEnum):
    """Modo usado por una pasada de CurrentVisualPrice."""

    DYNAMIC = "dynamic"
    FIXED_OVERRIDE = "fixed_override"


class CurrentVisualPriceSemanticResolutionStatus(StrEnum):
    """Resultado de deduplicar detecciones por identidad física."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    AMBIGUOUS = "ambiguous"
    BYPASSED = "bypassed"


class CurrentVisualPriceSemanticResolutionReason(StrEnum):
    """Razón final de la resolución semántica."""

    UNIQUE_SEMANTIC_PRICE = "unique_semantic_price"
    MULTIPLE_SEMANTIC_PRICES = "multiple_semantic_prices"
    NO_QUALIFYING_CANDIDATES = "no_qualifying_candidates"
    SEARCH_PLAN_UNAVAILABLE = "search_plan_unavailable"
    FIXED_OVERRIDE = "fixed_override"


@dataclass(frozen=True, slots=True)
class CurrentVisualPriceSearchConstraints:
    """Restricciones ya existentes necesarias para proponer ventanas."""

    image_width: int
    image_height: int
    right_band_ratio: float
    max_line_gap_ratio: float
    max_line_start_offset_ratio: float
    min_line_run_ratio: float
    label_zone_ratio: float
    label_vertical_radius_ratio: float
    max_row_gap_px: int
    max_candidate_height_px: int
    max_unique_windows: int = 32

    def __post_init__(self) -> None:
        if self.image_width < 1 or self.image_height < 1:
            raise ValueError("La geometría de búsqueda debe ser positiva.")
        ratios = (
            self.right_band_ratio,
            self.max_line_gap_ratio,
            self.max_line_start_offset_ratio,
            self.min_line_run_ratio,
            self.label_zone_ratio,
            self.label_vertical_radius_ratio,
        )
        if not all(isfinite(value) and 0.0 <= value <= 1.0 for value in ratios):
            raise ValueError("Los ratios de búsqueda deben estar entre 0 y 1.")
        if self.right_band_ratio == 0.0 or self.label_zone_ratio == 0.0:
            raise ValueError("Las ratios de banda y etiqueta deben ser positivas.")
        if self.max_row_gap_px < 0 or self.max_candidate_height_px < 0:
            raise ValueError("Los límites enteros de búsqueda no pueden ser negativos.")
        if self.max_unique_windows < 1:
            raise ValueError("max_unique_windows debe ser positivo.")


@dataclass(frozen=True, slots=True)
class CurrentVisualPriceLineRun:
    """Run global de máscara que conserva coordenadas half-open."""

    row_y: int
    start_x: int
    end_x: int

    def __post_init__(self) -> None:
        if self.row_y < 0 or self.start_x < 0 or self.end_x <= self.start_x:
            raise ValueError("El run horizontal es inválido.")


@dataclass(frozen=True, slots=True)
class CurrentVisualPriceLineHypothesis:
    """Identidad física de una línea formada por runs compatibles."""

    hypothesis_id: str
    runs: tuple[CurrentVisualPriceLineRun, ...]

    def __post_init__(self) -> None:
        if not self.hypothesis_id:
            raise ValueError("hypothesis_id no puede estar vacío.")
        if not self.runs:
            raise ValueError("Una hipótesis de línea requiere runs.")
        ordered = tuple(sorted(self.runs, key=lambda run: (run.row_y, run.start_x)))
        if self.runs != ordered or len(self.runs) != len(set(self.runs)):
            raise ValueError("Los runs deben ser únicos y estar ordenados.")


@dataclass(frozen=True, slots=True)
class CurrentVisualPriceLabelComponent:
    """Componente residual off-line que puede soportar una etiqueta."""

    component_id: str
    x: int
    y: int
    width: int
    height: int
    area: int

    def __post_init__(self) -> None:
        if not self.component_id:
            raise ValueError("component_id no puede estar vacío.")
        if min(self.x, self.y) < 0 or min(self.width, self.height, self.area) < 1:
            raise ValueError("La geometría del componente es inválida.")

    @property
    def end_x(self) -> int:
        return self.x + self.width

    @property
    def end_y(self) -> int:
        return self.y + self.height


@dataclass(frozen=True, slots=True)
class CurrentVisualPriceSearchWindow:
    """Ventana canónica half-open; su ID no identifica un precio."""

    window_id: str
    start_x: int
    end_x: int
    origin: CurrentVisualPriceSearchWindowOrigin
    line_hypothesis_ids: tuple[str, ...] = ()
    label_component_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.window_id:
            raise ValueError("window_id no puede estar vacío.")
        if self.start_x < 0 or self.end_x <= self.start_x:
            raise ValueError("La ventana de búsqueda es inválida.")
        for name, identifiers in (
            ("line_hypothesis_ids", self.line_hypothesis_ids),
            ("label_component_ids", self.label_component_ids),
        ):
            if any(not identifier for identifier in identifiers):
                raise ValueError(f"{name} contiene un ID vacío.")
            if len(identifiers) != len(set(identifiers)):
                raise ValueError(f"{name} contiene IDs duplicados.")
        if self.origin is CurrentVisualPriceSearchWindowOrigin.SEMANTIC_LINE_LABEL_PAIR:
            if not self.line_hypothesis_ids or not self.label_component_ids:
                raise ValueError("Una ventana semántica requiere provenance completa.")
        elif self.line_hypothesis_ids or self.label_component_ids:
            raise ValueError("Un override fijo no debe fingir provenance semántica.")

    @property
    def width(self) -> int:
        return self.end_x - self.start_x


@dataclass(frozen=True, slots=True)
class CurrentVisualPriceSearchPlan:
    """Plan determinístico de ventanas o indisponibilidad fail-closed."""

    status: CurrentVisualPriceSearchPlanStatus
    reason: CurrentVisualPriceSearchPlanReason
    constraints: CurrentVisualPriceSearchConstraints
    windows: tuple[CurrentVisualPriceSearchWindow, ...]
    line_hypotheses: tuple[CurrentVisualPriceLineHypothesis, ...] = ()
    label_components: tuple[CurrentVisualPriceLabelComponent, ...] = ()
    total_proposed_window_count: int = 0
    full_window_set_sha256: str | None = None

    def __post_init__(self) -> None:
        if self.total_proposed_window_count < len(self.windows):
            raise ValueError("El total propuesto no puede ser menor que el resumen.")
        if len({window.window_id for window in self.windows}) != len(self.windows):
            raise ValueError("Los window_id del plan deben ser únicos.")
        if len({(window.start_x, window.end_x) for window in self.windows}) != len(
            self.windows
        ):
            raise ValueError("El plan debe contener ventanas geométricas únicas.")
        if any(window.end_x > self.constraints.image_width for window in self.windows):
            raise ValueError("Una ventana excede image_width.")
        if self.status is CurrentVisualPriceSearchPlanStatus.AVAILABLE:
            if not self.windows or self.total_proposed_window_count != len(
                self.windows
            ):
                raise ValueError("Un plan disponible debe exponer todas sus ventanas.")
        elif self.reason is CurrentVisualPriceSearchPlanReason.WINDOW_LIMIT_EXCEEDED:
            if self.total_proposed_window_count <= self.constraints.max_unique_windows:
                raise ValueError("WINDOW_LIMIT_EXCEEDED requiere superar el límite.")
            if self.full_window_set_sha256 is None:
                raise ValueError("El conjunto excedido requiere un digest completo.")
        elif self.windows or self.total_proposed_window_count:
            raise ValueError(
                "Un plan no disponible no debe exponer ventanas parciales."
            )


@dataclass(frozen=True, slots=True)
class CurrentVisualPriceSearchWindowEvaluationTrace:
    """Resumen de qualification sin duplicar la traza completa de filas."""

    window_id: str
    decision_diagnostic: str
    candidate_count: int
    semantic_candidate_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.window_id or not self.decision_diagnostic:
            raise ValueError("La evaluación requiere IDs y diagnóstico.")
        if self.candidate_count < 0:
            raise ValueError("candidate_count no puede ser negativo.")
        if self.candidate_count != len(self.semantic_candidate_ids):
            raise ValueError("candidate_count no coincide con semantic_candidate_ids.")
        if len(self.semantic_candidate_ids) != len(set(self.semantic_candidate_ids)):
            raise ValueError("Los IDs semánticos de ventana deben ser únicos.")


@dataclass(frozen=True, slots=True)
class CurrentVisualPriceSemanticCandidateGroupTrace:
    """Cierre transitivo de detecciones con provenance física compartida."""

    group_id: str
    semantic_candidate_ids: tuple[str, ...]
    line_hypothesis_ids: tuple[str, ...]
    window_ids: tuple[str, ...]
    representative_window_id: str

    def __post_init__(self) -> None:
        if not self.group_id or not self.representative_window_id:
            raise ValueError("El grupo semántico requiere IDs.")
        for values in (
            self.semantic_candidate_ids,
            self.line_hypothesis_ids,
            self.window_ids,
        ):
            if not values or len(values) != len(set(values)):
                raise ValueError("La provenance semántica debe ser no vacía y única.")
        if self.representative_window_id not in self.window_ids:
            raise ValueError("La ventana representativa debe pertenecer al grupo.")


@dataclass(frozen=True, slots=True)
class CurrentVisualPriceSemanticSearchTrace:
    """Traza aditiva completa del proposal y la resolución semántica."""

    mode: CurrentVisualPriceSemanticSearchMode
    plan_status: CurrentVisualPriceSearchPlanStatus
    plan_reason: CurrentVisualPriceSearchPlanReason
    total_proposed_window_count: int
    evaluated_window_count: int
    windows: tuple[CurrentVisualPriceSearchWindow, ...]
    window_evaluations: tuple[CurrentVisualPriceSearchWindowEvaluationTrace, ...]
    semantic_groups: tuple[CurrentVisualPriceSemanticCandidateGroupTrace, ...]
    resolution_status: CurrentVisualPriceSemanticResolutionStatus
    resolution_reason: CurrentVisualPriceSemanticResolutionReason
    selected_group_id: str | None = None
    full_window_set_sha256: str | None = None

    def __post_init__(self) -> None:
        if min(self.total_proposed_window_count, self.evaluated_window_count) < 0:
            raise ValueError("Los conteos de búsqueda no pueden ser negativos.")
        if self.evaluated_window_count != len(self.window_evaluations):
            raise ValueError("evaluated_window_count es inconsistente.")
        window_ids = {window.window_id for window in self.windows}
        if any(item.window_id not in window_ids for item in self.window_evaluations):
            raise ValueError("Una evaluación referencia una ventana desconocida.")
        group_ids = {group.group_id for group in self.semantic_groups}
        if (
            self.selected_group_id is not None
            and self.selected_group_id not in group_ids
        ):
            raise ValueError("selected_group_id no pertenece a los grupos.")
        if (
            self.resolution_status
            is CurrentVisualPriceSemanticResolutionStatus.AVAILABLE
        ):
            if len(self.semantic_groups) != 1 or self.selected_group_id is None:
                raise ValueError("AVAILABLE requiere un único grupo seleccionado.")
        elif self.selected_group_id is not None:
            raise ValueError("Sólo AVAILABLE puede seleccionar un grupo.")
