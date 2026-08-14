from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CurrentVisualPriceComparisonStatus(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class CurrentVisualPriceComparisonDiagnostic(StrEnum):
    COMPARISON_AVAILABLE = "comparison_available"
    ENTRY_CONTEXT_MISSING = "entry_context_missing"
    EXIT_CONTEXT_MISSING = "exit_context_missing"
    ENTRY_EXTRACTION_UNAVAILABLE = "entry_extraction_unavailable"
    EXIT_EXTRACTION_UNAVAILABLE = "exit_extraction_unavailable"
    ENTRY_GEOMETRY_MISSING = "entry_geometry_missing"
    EXIT_GEOMETRY_MISSING = "exit_geometry_missing"
    ENTRY_GEOMETRY_INCOHERENT = "entry_geometry_incoherent"
    EXIT_GEOMETRY_INCOHERENT = "exit_geometry_incoherent"
    ENTRY_REFERENCE_UNAVAILABLE = "entry_reference_unavailable"
    EXIT_REFERENCE_UNAVAILABLE = "exit_reference_unavailable"
    ENTRY_ANCHORS_MISSING = "entry_anchors_missing"
    EXIT_ANCHORS_MISSING = "exit_anchors_missing"
    ENTRY_ANCHORS_DEGENERATE = "entry_anchors_degenerate"
    EXIT_ANCHORS_DEGENERATE = "exit_anchors_degenerate"
    ENTRY_ANCHORS_INCOHERENT = "entry_anchors_incoherent"
    EXIT_ANCHORS_INCOHERENT = "exit_anchors_incoherent"
    REFERENCES_NOT_COMPARABLE = "references_not_comparable"
    SOURCES_NOT_COMPARABLE = "sources_not_comparable"


@dataclass(frozen=True, slots=True)
class CurrentVisualPriceComparison:
    """Auditable canonical price evidence from entry and expiry frames."""

    status: CurrentVisualPriceComparisonStatus
    diagnostic: CurrentVisualPriceComparisonDiagnostic
    entry_anchored_value: float | None = None
    exit_anchored_value: float | None = None
    delta: float | None = None
    entry_price_y_in_chart_roi: float | None = None
    exit_price_y_in_chart_roi: float | None = None

    def __post_init__(self) -> None:
        if self.status is CurrentVisualPriceComparisonStatus.AVAILABLE:
            if (
                self.diagnostic
                is not CurrentVisualPriceComparisonDiagnostic.COMPARISON_AVAILABLE
            ):
                raise ValueError(
                    "AVAILABLE requiere el diagnóstico COMPARISON_AVAILABLE."
                )
            required_numbers = (
                self.entry_price_y_in_chart_roi,
                self.exit_price_y_in_chart_roi,
                self.entry_anchored_value,
                self.exit_anchored_value,
                self.delta,
            )
            if any(value is None for value in required_numbers):
                raise ValueError(
                    "AVAILABLE requiere todas las coordenadas y valores numéricos."
                )
            return

        if self.status is not CurrentVisualPriceComparisonStatus.UNAVAILABLE:
            raise ValueError("status debe ser AVAILABLE o UNAVAILABLE.")
        if (
            self.diagnostic
            is CurrentVisualPriceComparisonDiagnostic.COMPARISON_AVAILABLE
        ):
            raise ValueError(
                "UNAVAILABLE no admite el diagnóstico COMPARISON_AVAILABLE."
            )
        if self.delta is not None:
            raise ValueError("UNAVAILABLE requiere delta=None.")

        sides = (
            (
                "entry",
                self.entry_price_y_in_chart_roi,
                self.entry_anchored_value,
            ),
            (
                "exit",
                self.exit_price_y_in_chart_roi,
                self.exit_anchored_value,
            ),
        )
        for side, coordinate, anchored_value in sides:
            if (coordinate is None) != (anchored_value is None):
                raise ValueError(
                    f"{side} requiere coordenada y valor anclado coherentes."
                )
