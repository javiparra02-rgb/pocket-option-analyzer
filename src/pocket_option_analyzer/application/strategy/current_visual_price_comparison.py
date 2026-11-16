from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite
from numbers import Real

from .visual_scale_signature import (
    EvidenceScope,
    MeasurementValidity,
    MeasurementValidityResult,
    VisualPriceCompatibility,
    VisualScaleRelationEvidence,
)


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
    INVALID_INPUT = "invalid_input"


@dataclass(frozen=True, slots=True)
class CurrentVisualPriceComparison:
    """AVAILABLE/delta retain legacy GEOMETRIC DIAGNOSTIC semantics.

    Only accredited_delta/has_accredited_comparison describe usable comparison.
    Deserialized or manually built legacy results are unverified by default.
    """

    status: CurrentVisualPriceComparisonStatus
    diagnostic: CurrentVisualPriceComparisonDiagnostic
    entry_anchored_value: float | None = None
    exit_anchored_value: float | None = None
    delta: float | None = None
    entry_price_y_in_chart_roi: float | None = None
    exit_price_y_in_chart_roi: float | None = None
    entry_anchor_span_px: float | None = None
    exit_anchor_span_px: float | None = None
    entry_validity: MeasurementValidityResult = field(
        default_factory=MeasurementValidityResult, kw_only=True,
    )
    exit_validity: MeasurementValidityResult = field(
        default_factory=MeasurementValidityResult, kw_only=True,
    )
    compatibility: VisualPriceCompatibility = field(
        default=VisualPriceCompatibility.UNDETERMINED, kw_only=True,
    )
    compatibility_reasons: tuple[str, ...] = field(
        default=("RELATIONAL_EVIDENCE_MISSING",), kw_only=True,
    )
    evidence_scope: EvidenceScope = field(default=EvidenceScope.PRODUCTION, kw_only=True)
    relation_evidence: VisualScaleRelationEvidence | None = field(
        default=None, kw_only=True,
    )
    verification_references: tuple[str, ...] = field(default=(), kw_only=True)
    accredited_delta: float | None = field(default=None, kw_only=True)

    @property
    def has_accredited_comparison(self) -> bool:
        return (
            self.evidence_scope is EvidenceScope.PRODUCTION
            and self.compatibility is VisualPriceCompatibility.COMPATIBLE
            and self.entry_validity.state is MeasurementValidity.VALID
            and self.exit_validity.state is MeasurementValidity.VALID
            and self.accredited_delta is not None
        )

    def __post_init__(self) -> None:
        if (
            not isinstance(self.entry_validity, MeasurementValidityResult)
            or not isinstance(self.exit_validity, MeasurementValidityResult)
            or not isinstance(self.compatibility, VisualPriceCompatibility)
            or not isinstance(self.evidence_scope, EvidenceScope)
        ):
            raise ValueError("Invalid explicit comparison contract")
        for values in (self.compatibility_reasons, self.verification_references):
            if type(values) is not tuple or any(type(v) is not str for v in values):
                raise ValueError("Explicit comparison diagnostics must be immutable")
        if self.relation_evidence is not None and not isinstance(
            self.relation_evidence, VisualScaleRelationEvidence,
        ):
            raise ValueError("Unsupported relational evidence schema")
        if self.compatibility is VisualPriceCompatibility.INCOMPATIBLE and (
            not self.compatibility_reasons or not self.verification_references
            or self.relation_evidence is None
            or self.relation_evidence.scope is not self.evidence_scope
            or (self.evidence_scope is EvidenceScope.PRODUCTION
                and self.relation_evidence.provenance == "TEST_ONLY")
        ):
            raise ValueError("Incompatibility requires applicable contradiction evidence")
        if self.compatibility is VisualPriceCompatibility.COMPATIBLE and (
            self.compatibility_reasons
            or self.entry_validity.state is not MeasurementValidity.VALID
            or self.exit_validity.state is not MeasurementValidity.VALID
            or not self.verification_references
            or not isinstance(self.relation_evidence, VisualScaleRelationEvidence)
            or self.relation_evidence.scope is not self.evidence_scope
            or (self.evidence_scope is EvidenceScope.PRODUCTION
                and self.relation_evidence.provenance == "TEST_ONLY")
        ):
            raise ValueError("Compatibility requires applicable relational evidence")
        if self.accredited_delta is not None:
            if (
                not self.has_accredited_comparison
                or not self.verification_references
                or self.relation_evidence is None
                or isinstance(self.accredited_delta, bool)
                or not isinstance(self.accredited_delta, Real)
                or not isfinite(self.accredited_delta)
                or self.entry_anchored_value is None
                or self.exit_anchored_value is None
                or self.accredited_delta != (
                    self.exit_anchored_value - self.entry_anchored_value
                )
            ):
                raise ValueError("Accredited delta requires verified production evidence")
        numeric_evidence = (
            ("entry_anchored_value", self.entry_anchored_value),
            ("exit_anchored_value", self.exit_anchored_value),
            ("delta", self.delta),
            ("entry_price_y_in_chart_roi", self.entry_price_y_in_chart_roi),
            ("exit_price_y_in_chart_roi", self.exit_price_y_in_chart_roi),
            ("entry_anchor_span_px", self.entry_anchor_span_px),
            ("exit_anchor_span_px", self.exit_anchor_span_px),
        )
        for field_name, value in numeric_evidence:
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, Real)
                or not isfinite(value)
            ):
                raise ValueError(f"{field_name} debe ser un número finito.")

        spans = (
            ("entry_anchor_span_px", self.entry_anchor_span_px),
            ("exit_anchor_span_px", self.exit_anchor_span_px),
        )
        for field_name, span in spans:
            if span is not None and span <= 0:
                raise ValueError(f"{field_name} debe ser mayor que cero.")

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
                self.entry_anchor_span_px,
                self.exit_anchor_span_px,
            )
            if any(value is None for value in required_numbers):
                raise ValueError(
                    "AVAILABLE requiere todas las coordenadas, valores y spans."
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
                self.entry_anchor_span_px,
            ),
            (
                "exit",
                self.exit_price_y_in_chart_roi,
                self.exit_anchored_value,
                self.exit_anchor_span_px,
            ),
        )
        for side, coordinate, anchored_value, anchor_span in sides:
            if (coordinate is None) != (anchored_value is None):
                raise ValueError(
                    f"{side} requiere coordenada y valor anclado coherentes."
                )
            if anchor_span is not None and coordinate is None:
                raise ValueError(
                    f"{side} no admite span sin evidencia normalizada coherente."
                )
