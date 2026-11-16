from __future__ import annotations

from dataclasses import dataclass, replace
from math import isfinite
from numbers import Real
from typing import Literal

from .current_visual_price_comparison import (
    CurrentVisualPriceComparison,
    CurrentVisualPriceComparisonDiagnostic,
    CurrentVisualPriceComparisonStatus,
)
from .current_visual_price_comparison_context import (
    CurrentVisualPriceComparisonContext,
)
from .strategy_observation_outcome import VisualPriceReference
from .visual_reference_validation import references_are_comparable
from .visual_scale_signature import (
    RELATION_CLAIMS,
    EvidenceScope,
    EvidenceVerification,
    MeasurementValidity,
    MeasurementValidityResult,
    ScaleEvidenceAssessment,
    VisualMeasurementIdentity,
    VisualPriceCompatibility,
    VisualScaleEvidenceVerifier,
    VisualScaleRelationEvidence,
    VisualScaleSignature,
)

_Side = Literal["entry", "exit"]
_Failure = Literal[
    "extraction_unavailable",
    "geometry_missing",
    "geometry_incoherent",
    "reference_unavailable",
    "anchors_missing",
    "anchors_degenerate",
    "anchors_incoherent",
]


@dataclass(frozen=True, slots=True)
class _CanonicalVisualPrice:
    anchored_value: float
    price_y_in_chart_roi: float
    anchor_span_px: float
    source: str
    reference: VisualPriceReference


class CurrentVisualPriceComparator:
    """Legacy geometry plus a separate, fail-closed evidence decision.

    AVAILABLE/delta remain diagnostic for existing consumers. Production use
    requires has_accredited_comparison. No production verifier is supplied.
    """

    def __init__(
        self, evidence_verifier: VisualScaleEvidenceVerifier | None = None,
        *, evidence_scope: EvidenceScope = EvidenceScope.PRODUCTION,
    ) -> None:
        if not isinstance(evidence_scope, EvidenceScope):
            raise ValueError("Invalid evidence scope")
        self._evidence_verifier = evidence_verifier
        self._evidence_scope = evidence_scope

    def compare(
        self,
        entry_context: CurrentVisualPriceComparisonContext | None,
        exit_context: CurrentVisualPriceComparisonContext | None,
        *, relation_evidence: VisualScaleRelationEvidence | None = None,
    ) -> CurrentVisualPriceComparison:
        # getattr retains compatibility with legacy subclasses that override
        # __init__ without calling super(). It never supplies a verifier.
        scope = getattr(self, "_evidence_scope", EvidenceScope.PRODUCTION)
        verifier = getattr(self, "_evidence_verifier", None)
        entry_validity = self._individual(entry_context, verifier, scope)
        exit_validity = self._individual(exit_context, verifier, scope)
        try:
            geometry = self._compare_geometry(entry_context, exit_context)
        except (ValueError, TypeError, ArithmeticError):
            geometry = self._unavailable(CurrentVisualPriceComparisonDiagnostic.INVALID_INPUT)

        compatibility, reasons, references = self._relation(
            entry_context, exit_context, entry_validity, exit_validity,
            relation_evidence, verifier, scope,
        )
        accredited_delta = None
        if compatibility is VisualPriceCompatibility.COMPATIBLE:
            # The supported proof attests this precise per-frame affine basis;
            # it is not a license to invent other transforms or clamp breakouts.
            assert entry_context is not None and exit_context is not None
            try:
                entry, _ = self._canonical_value(entry_context, side="entry")
                exit, _ = self._canonical_value(exit_context, side="exit")
            except (ValueError, TypeError, ArithmeticError):
                entry, exit = None, None
            if entry is None or exit is None:
                compatibility = VisualPriceCompatibility.UNDETERMINED
                reasons = ("CANONICAL_GEOMETRY_UNAVAILABLE",)
            elif scope is EvidenceScope.PRODUCTION:
                candidate = exit.anchored_value - entry.anchored_value
                if isfinite(candidate):
                    accredited_delta = candidate
                else:
                    compatibility = VisualPriceCompatibility.UNDETERMINED
                    reasons = ("NONFINITE_CANONICAL_DELTA",)

        return replace(
            geometry, entry_validity=entry_validity, exit_validity=exit_validity,
            compatibility=compatibility, compatibility_reasons=reasons,
            evidence_scope=scope, relation_evidence=(
                relation_evidence
                if isinstance(relation_evidence, VisualScaleRelationEvidence)
                else None
            ),
            verification_references=references, accredited_delta=accredited_delta,
        )

    @staticmethod
    def _assessment_matches(
        assessment: ScaleEvidenceAssessment,
        signatures: tuple[VisualScaleSignature, ...], scope: EvidenceScope,
    ) -> bool:
        return (
            isinstance(assessment, ScaleEvidenceAssessment)
            and assessment.scope is scope
            and assessment.identities == tuple(s.identity for s in signatures)
            and assessment.signature_references == tuple(
                s.signature_reference for s in signatures
            )
            and isinstance(assessment.evidence_reference, str)
            and bool(assessment.evidence_reference.strip())
            and type(assessment.covered_claims) is tuple
            and all(type(c) is str for c in assessment.covered_claims)
        )

    @staticmethod
    def _verifier_available(
        verifier: VisualScaleEvidenceVerifier | None, scope: EvidenceScope,
    ) -> bool:
        try:
            return isinstance(verifier, VisualScaleEvidenceVerifier) and verifier.scope is scope
        except Exception:
            return False

    @classmethod
    def _individual(
        cls, context: CurrentVisualPriceComparisonContext | None,
        verifier: VisualScaleEvidenceVerifier | None, scope: EvidenceScope,
    ) -> MeasurementValidityResult:
        def result(state: MeasurementValidity, *reasons: str) -> MeasurementValidityResult:
            return MeasurementValidityResult(state, tuple(reasons))

        if context is None or context.current_visual_price is None:
            return result(MeasurementValidity.UNDETERMINED, "EXTRACTION_MISSING")
        extraction = context.current_visual_price
        if not extraction.is_available or extraction.price is None:
            return result(MeasurementValidity.INVALID, "EXTRACTION_UNAVAILABLE")
        price = extraction.price
        if (
            any(isinstance(v, bool) or not isinstance(v, Real) or not isfinite(v)
                for v in (price.roi_y, price.normalized_roi_y))
            or type(price.roi_width) is not int or price.roi_width <= 0
            or type(price.roi_height) is not int or price.roi_height <= 1
            or not 0 <= price.roi_y <= price.roi_height - 1
            or not 0 <= price.normalized_roi_y <= 1
        ):
            return result(MeasurementValidity.INVALID, "INVALID_COORDINATES")
        # Accept the two explicit algebraic evaluation orders, not a noise
        # epsilon. No pixel tolerance or scale calibration is introduced.
        if price.normalized_roi_y not in (
            1.0 - price.roi_y / (price.roi_height - 1),
            (price.roi_height - 1 - price.roi_y) / (price.roi_height - 1),
        ):
            return result(MeasurementValidity.INVALID, "NORMALIZATION_INCOHERENT")
        if context.price_observation_region is None or context.chart_region is None:
            return result(MeasurementValidity.UNDETERMINED, "GEOMETRY_MISSING")
        region = context.price_observation_region
        chart = context.chart_region
        if (
            not region.has_positive_area or not chart.has_positive_area
            or min(region.x, region.y, chart.x, chart.y) < 0
            or region.width != price.roi_width or region.height != price.roi_height
        ):
            return result(MeasurementValidity.INVALID, "GEOMETRY_INCOHERENT")
        signature = context.scale_signature
        if not isinstance(signature, VisualScaleSignature):
            return result(MeasurementValidity.UNDETERMINED, "SIGNATURE_MISSING")
        expected_identity = VisualMeasurementIdentity(
            context.execution_id, context.session_key, context.source_key,
            context.frame_id,
        )
        reference = context.reference_result.reference
        if (
            signature.identity != expected_identity
            or signature.price_region != region or signature.chart_region != chart
            or signature.extraction_source != price.source
            or signature.anchors != (reference.anchor_shape if reference else ())
            or signature.anchor_top_roi_y != context.reference_result.anchor_top_roi_y
            or signature.anchor_bottom_roi_y != context.reference_result.anchor_bottom_roi_y
            or signature.coordinate_system != "PRICE_OBSERVATION_ROI_LOCAL_PIXELS"
            or signature.normalization != "ONE_MINUS_Y_OVER_HEIGHT_MINUS_ONE"
        ):
            return result(MeasurementValidity.INVALID, "SIGNATURE_BINDING_CONFLICT")
        if (
            not signature.identity.is_complete
            or not signature.signature_reference
            or not signature.extraction_method or not signature.extraction_version
            or signature.effective_configuration is None
            or not signature.provenance or not signature.source_provenance
            or not signature.parent_coordinate_system
        ):
            return result(MeasurementValidity.UNDETERMINED, "SIGNATURE_INCOMPLETE")
        if scope is EvidenceScope.PRODUCTION and (
            signature.provenance == "TEST_ONLY"
            or signature.source_provenance == "TEST_ONLY"
        ):
            return result(MeasurementValidity.UNDETERMINED, "TEST_ONLY_NOT_PRODUCTIVE")
        if not cls._verifier_available(verifier, scope):
            return result(MeasurementValidity.UNDETERMINED, "PROVENANCE_UNVERIFIED")
        try:
            assert verifier is not None
            assessment = verifier.verify_measurement(
                signature, roi_y=price.roi_y,
                normalized_roi_y=price.normalized_roi_y,
            )
        except Exception:
            return result(MeasurementValidity.UNDETERMINED, "PROVENANCE_VERIFIER_ERROR")
        if not cls._assessment_matches(assessment, (signature,), scope):
            return result(MeasurementValidity.UNDETERMINED, "PROVENANCE_RECEIPT_UNBOUND")
        if "measurement_provenance" not in assessment.covered_claims:
            return result(MeasurementValidity.UNDETERMINED, "PROVENANCE_UNVERIFIED")
        if assessment.status is EvidenceVerification.CONTRADICTED:
            return result(MeasurementValidity.INVALID, "PROVENANCE_CONTRADICTED")
        if assessment.status is not EvidenceVerification.VERIFIED:
            return result(MeasurementValidity.UNDETERMINED, "PROVENANCE_UNVERIFIED")
        return MeasurementValidityResult(
            MeasurementValidity.VALID, (), (assessment.evidence_reference,),
        )

    @classmethod
    def _relation(
        cls, entry: CurrentVisualPriceComparisonContext | None,
        exit: CurrentVisualPriceComparisonContext | None,
        entry_validity: MeasurementValidityResult,
        exit_validity: MeasurementValidityResult,
        evidence: VisualScaleRelationEvidence | None,
        verifier: VisualScaleEvidenceVerifier | None, scope: EvidenceScope,
    ) -> tuple[VisualPriceCompatibility, tuple[str, ...], tuple[str, ...]]:
        unknown = VisualPriceCompatibility.UNDETERMINED
        if evidence is None:
            return unknown, ("RELATIONAL_EVIDENCE_MISSING",), ()
        if not isinstance(evidence, VisualScaleRelationEvidence):
            return unknown, ("RELATIONAL_EVIDENCE_SCHEMA_UNSUPPORTED",), ()
        if evidence.scope is not scope or (
            scope is EvidenceScope.PRODUCTION and evidence.provenance == "TEST_ONLY"
        ):
            return unknown, ("EVIDENCE_SCOPE_NOT_APPLICABLE",), ()
        if (
            entry_validity.state is not MeasurementValidity.VALID
            or exit_validity.state is not MeasurementValidity.VALID
        ):
            return unknown, ("INDIVIDUAL_VALIDITY_NOT_ESTABLISHED",), ()
        if entry is None or exit is None:
            return unknown, ("SIGNATURE_MISSING",), ()
        a, b = entry.scale_signature, exit.scale_signature
        if not isinstance(a, VisualScaleSignature) or not isinstance(b, VisualScaleSignature):
            return unknown, ("SIGNATURE_MISSING",), ()
        if (
            evidence.schema_version != 1
            or evidence.entry_identity != a.identity
            or evidence.exit_identity != b.identity
            or evidence.entry_signature_reference != a.signature_reference
            or evidence.exit_signature_reference != b.signature_reference
            or not evidence.evidence_reference or not evidence.provenance
            or evidence.relation_type != "SAME_ANCHOR_AFFINE_V1"
        ):
            return unknown, ("RELATIONAL_EVIDENCE_UNBOUND_OR_UNSUPPORTED",), ()
        if not cls._verifier_available(verifier, scope):
            return unknown, ("RELATION_VERIFIER_UNAVAILABLE",), ()
        try:
            assert verifier is not None
            assessment = verifier.verify_relation(evidence, a, b)
        except Exception:
            return unknown, ("RELATION_VERIFIER_ERROR",), ()
        if (
            not cls._assessment_matches(assessment, (a, b), scope)
            or assessment.evidence_reference != evidence.evidence_reference
        ):
            return unknown, ("RELATIONAL_RECEIPT_UNBOUND",), ()
        claims = set(assessment.covered_claims)
        if assessment.status is EvidenceVerification.CONTRADICTED and claims & RELATION_CLAIMS:
            return VisualPriceCompatibility.INCOMPATIBLE, ("VERIFIED_RELATIONAL_CONTRADICTION",), (assessment.evidence_reference,)
        if assessment.status is EvidenceVerification.VERIFIED and RELATION_CLAIMS <= claims:
            return VisualPriceCompatibility.COMPATIBLE, (), (assessment.evidence_reference,)
        return unknown, ("COMMON_BASIS_NOT_VERIFIED",), ()

    def _compare_geometry(
        self,
        entry_context: CurrentVisualPriceComparisonContext | None,
        exit_context: CurrentVisualPriceComparisonContext | None,
    ) -> CurrentVisualPriceComparison:
        if entry_context is None:
            return self._unavailable(
                CurrentVisualPriceComparisonDiagnostic.ENTRY_CONTEXT_MISSING,
            )
        if exit_context is None:
            return self._unavailable(
                CurrentVisualPriceComparisonDiagnostic.EXIT_CONTEXT_MISSING,
            )

        entry, diagnostic = self._canonical_value(entry_context, side="entry")
        if entry is None:
            assert diagnostic is not None
            return self._unavailable(diagnostic)

        exit, diagnostic = self._canonical_value(exit_context, side="exit")
        if exit is None:
            assert diagnostic is not None
            return self._unavailable(diagnostic, entry=entry)

        if entry.source != exit.source:
            return self._unavailable(
                CurrentVisualPriceComparisonDiagnostic.SOURCES_NOT_COMPARABLE,
                entry=entry,
                exit=exit,
            )
        if not references_are_comparable(entry.reference, exit.reference):
            return self._unavailable(
                CurrentVisualPriceComparisonDiagnostic.REFERENCES_NOT_COMPARABLE,
                entry=entry,
                exit=exit,
            )

        return CurrentVisualPriceComparison(
            status=CurrentVisualPriceComparisonStatus.AVAILABLE,
            diagnostic=(
                CurrentVisualPriceComparisonDiagnostic.COMPARISON_AVAILABLE
            ),
            entry_anchored_value=entry.anchored_value,
            exit_anchored_value=exit.anchored_value,
            delta=exit.anchored_value - entry.anchored_value,
            entry_price_y_in_chart_roi=entry.price_y_in_chart_roi,
            exit_price_y_in_chart_roi=exit.price_y_in_chart_roi,
            entry_anchor_span_px=entry.anchor_span_px,
            exit_anchor_span_px=exit.anchor_span_px,
        )

    @staticmethod
    def _canonical_value(
        context: CurrentVisualPriceComparisonContext,
        *,
        side: _Side,
    ) -> tuple[
        _CanonicalVisualPrice | None,
        CurrentVisualPriceComparisonDiagnostic | None,
    ]:
        extraction = context.current_visual_price
        if extraction is None or not extraction.is_available:
            return None, _diagnostic(side, "extraction_unavailable")
        price = extraction.price
        if price is None:
            return None, _diagnostic(side, "extraction_unavailable")

        chart_region = context.chart_region
        price_region = context.price_observation_region
        if chart_region is None or price_region is None:
            return None, _diagnostic(side, "geometry_missing")
        if (
            chart_region.x < 0
            or chart_region.y < 0
            or price_region.x < 0
            or price_region.y < 0
            or not chart_region.has_positive_area
            or not price_region.has_positive_area
            or price.roi_width != price_region.width
            or price.roi_height != price_region.height
        ):
            return None, _diagnostic(side, "geometry_incoherent")

        price_y_in_chart_roi = price_region.y + price.roi_y - chart_region.y
        if not 0.0 <= price_y_in_chart_roi <= chart_region.height - 1:
            return None, _diagnostic(side, "geometry_incoherent")

        reference_result = context.reference_result
        if not reference_result.is_available:
            return None, _diagnostic(side, "reference_unavailable")
        reference = reference_result.reference
        if reference is None:
            return None, _diagnostic(side, "reference_unavailable")

        anchor_top = reference_result.anchor_top_roi_y
        anchor_bottom = reference_result.anchor_bottom_roi_y
        if anchor_top is None or anchor_bottom is None:
            return None, _diagnostic(side, "anchors_missing")
        if anchor_top == anchor_bottom:
            return None, _diagnostic(side, "anchors_degenerate")
        if (
            anchor_top < 0
            or anchor_bottom < 0
            or anchor_top > chart_region.height - 1
            or anchor_bottom > chart_region.height - 1
            or anchor_top > anchor_bottom
        ):
            return None, _diagnostic(side, "anchors_incoherent")

        anchored_value = (anchor_bottom - price_y_in_chart_roi) / (
            anchor_bottom - anchor_top
        )
        anchor_span_px = float(anchor_bottom - anchor_top)
        return (
            _CanonicalVisualPrice(
                anchored_value=anchored_value,
                price_y_in_chart_roi=price_y_in_chart_roi,
                anchor_span_px=anchor_span_px,
                source=price.source,
                reference=reference,
            ),
            None,
        )

    @staticmethod
    def _unavailable(
        diagnostic: CurrentVisualPriceComparisonDiagnostic,
        *,
        entry: _CanonicalVisualPrice | None = None,
        exit: _CanonicalVisualPrice | None = None,
    ) -> CurrentVisualPriceComparison:
        return CurrentVisualPriceComparison(
            status=CurrentVisualPriceComparisonStatus.UNAVAILABLE,
            diagnostic=diagnostic,
            entry_anchored_value=(
                entry.anchored_value if entry is not None else None
            ),
            exit_anchored_value=(
                exit.anchored_value if exit is not None else None
            ),
            delta=None,
            entry_price_y_in_chart_roi=(
                entry.price_y_in_chart_roi if entry is not None else None
            ),
            exit_price_y_in_chart_roi=(
                exit.price_y_in_chart_roi if exit is not None else None
            ),
            entry_anchor_span_px=(
                entry.anchor_span_px if entry is not None else None
            ),
            exit_anchor_span_px=(
                exit.anchor_span_px if exit is not None else None
            ),
        )


def _diagnostic(
    side: _Side,
    failure: _Failure,
) -> CurrentVisualPriceComparisonDiagnostic:
    return CurrentVisualPriceComparisonDiagnostic(f"{side}_{failure}")
