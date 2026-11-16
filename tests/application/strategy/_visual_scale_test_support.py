"""Shared SYNTHETIC_TEST_DATA helpers. TEST_ONLY, not a production verifier."""

from pocket_option_analyzer.application.strategy import (
    CurrentVisualPriceComparator,
    CurrentVisualPriceComparisonContext,
    VisualPriceReference,
    VisualPriceReferenceResult,
    VisualPriceReferenceStatus,
)
from pocket_option_analyzer.application.strategy.visual_scale_signature import (
    RELATION_CLAIMS,
    EvidenceScope,
    EvidenceVerification,
    ScaleEvidenceAssessment,
    VisualMeasurementIdentity,
    VisualScaleEvidenceVerifier,
    VisualScaleRelationEvidence,
    VisualScaleSignature,
)
from pocket_option_analyzer.vision.models import (
    ChartRegion,
    CurrentVisualPrice,
    CurrentVisualPriceExtraction,
    CurrentVisualPriceStatus,
)


def _context(frame=1, y=8.0):
    identity = VisualMeasurementIdentity("fixture-run", "fixture-session", "fixture-source", frame)
    reference = VisualPriceReference(0.5, (("bullish", 1.0, 0.8, 0.2, 0.0),))
    region = ChartRegion(3, 4, 16, 20)
    signature = VisualScaleSignature(
        signature_reference=f"fixture-signature-{frame}", identity=identity,
        extraction_method="fixture-extractor", extraction_version="fixture-v1",
        extraction_source="fixture-method-source",
        effective_configuration=(("fixture_parameter", True),),
        provenance="TEST_ONLY", source_provenance="TEST_ONLY",
        instrument_identity="fixture-context-not-a-financial-instrument",
        chart_region=region, price_region=region,
        parent_coordinate_system="FIXTURE_PARENT_IMAGE",
        anchors=reference.anchor_shape, anchor_top_roi_y=2, anchor_bottom_roi_y=18,
        anchor_provenance="TEST_ONLY", anchor_identities=("fixture-closed-anchor",),
        evidence_references=(f"fixture-provenance-{frame}",),
    )
    return CurrentVisualPriceComparisonContext(
        CurrentVisualPriceExtraction(
            CurrentVisualPrice(y, 1 - y / 19, 16, 20, "fixture-method-source", 0.99),
            CurrentVisualPriceStatus.OK,
        ), region, region,
        VisualPriceReferenceResult(
            reference, VisualPriceReferenceStatus.OK,
            anchor_top_roi_y=2, anchor_bottom_roi_y=18,
        ),
        execution_id=identity.execution_id, session_key=identity.session_key,
        source_key=identity.source_key, frame_id=frame, scale_signature=signature,
    )


def _relation(a, b):
    return VisualScaleRelationEvidence(
        a.scale_signature.identity, b.scale_signature.identity,
        a.scale_signature.signature_reference, b.scale_signature.signature_reference,
        "fixture-relation", "TEST_ONLY", EvidenceScope.TEST_ONLY,
        claimed_verification=EvidenceVerification.VERIFIED,
    )


class _FixtureVerifier(VisualScaleEvidenceVerifier):
    scope = EvidenceScope.TEST_ONLY

    def __init__(self, a, b, relation, *, contradiction=False, claims=None):
        self.contexts = (a, b)
        self.relation = relation
        self.contradiction = contradiction
        self.claims = tuple(sorted(RELATION_CLAIMS)) if claims is None else claims

    def verify_measurement(self, signature, *, roi_y, normalized_roi_y):
        registered = next(c for c in self.contexts if c.scale_signature is signature)
        assert registered.current_visual_price.price.roi_y == roi_y
        assert registered.current_visual_price.price.normalized_roi_y == normalized_roi_y
        return ScaleEvidenceAssessment(
            EvidenceVerification.VERIFIED, self.scope, (signature.identity,),
            (signature.signature_reference,), f"fixture-measurement-{signature.identity.frame_id}",
            ("measurement_provenance",),
        )

    def verify_relation(self, evidence, entry, exit):
        assert evidence is self.relation
        assert entry is self.contexts[0].scale_signature
        assert exit is self.contexts[1].scale_signature
        return ScaleEvidenceAssessment(
            EvidenceVerification.CONTRADICTED if self.contradiction else EvidenceVerification.VERIFIED,
            self.scope, (entry.identity, exit.identity),
            (entry.signature_reference, exit.signature_reference),
            evidence.evidence_reference, self.claims,
        )


def _synthetic_comparator(a, b, relation, **arguments):
    return CurrentVisualPriceComparator(
        _FixtureVerifier(a, b, relation, **arguments),
        evidence_scope=EvidenceScope.TEST_ONLY,
    )
