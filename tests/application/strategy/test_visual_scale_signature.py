"""SYNTHETIC_TEST_DATA only. No image, file, capture or external certifier.

The fixture verifier models a TEST_ONLY contract over registered objects. It is
not a real verifier and is never used to produce a production accreditation.
"""

from dataclasses import FrozenInstanceError, replace

import pytest

from pocket_option_analyzer.application.strategy import (
    CurrentVisualPriceComparator,
    CurrentVisualPriceComparisonStatus,
    PriceMovement,
    StrategyObservationOutcome,
    StrategyObservationOutcomeResolver,
    VisualPriceMovementClassifier,
)
from pocket_option_analyzer.application.strategy.visual_scale_signature import (
    EvidenceScope,
    MeasurementValidity,
    VisualPriceCompatibility,
    VisualScaleSignature,
)
from pocket_option_analyzer.domain.signals import SignalDirection
from pocket_option_analyzer.vision.models import (
    ChartRegion,
    CurrentVisualPriceExtraction,
    CurrentVisualPriceStatus,
)

from _visual_scale_test_support import (
    _context,
    _relation,
    _FixtureVerifier,
    _synthetic_comparator,
)


def test_complete_signature_is_descriptive_immutable_and_preserves_provenance():
    signature = _context().scale_signature
    assert signature.schema_version == 1
    assert signature.effective_configuration == (("fixture_parameter", True),)
    assert signature.provenance == "TEST_ONLY"
    assert signature.anchor_identities == ("fixture-closed-anchor",)
    with pytest.raises(FrozenInstanceError):
        signature.extraction_version = "changed"
    with pytest.raises(ValueError):
        replace(signature, effective_configuration=[("mutable", 1)])
    with pytest.raises(ValueError):
        replace(signature, provenance={"mutable": True})


def test_incomplete_signature_is_useful_but_not_a_certificate():
    signature = VisualScaleSignature()
    assert not signature.identity.is_complete
    assert signature.extraction_version is None
    assert signature.effective_configuration is None
    assert signature.scale_continuity_reference is None
    assert signature.noise_calibration_state.value == "UNCALIBRATED"


def test_equal_geometry_and_similar_anchors_only_produce_legacy_diagnostics():
    a, b = _context(), _context(2, 4.0)
    result = CurrentVisualPriceComparator().compare(a, b)
    assert result.status is CurrentVisualPriceComparisonStatus.AVAILABLE
    assert result.delta == 0.25
    assert result.compatibility is VisualPriceCompatibility.UNDETERMINED
    assert result.accredited_delta is None
    assert not result.has_accredited_comparison


def test_complete_declared_production_data_still_requires_a_verifier():
    a, b = _context(), _context(2)
    a = replace(a, scale_signature=replace(
        a.scale_signature, provenance="declared_same_pass", source_provenance="declared_source",
    ))
    b = replace(b, scale_signature=replace(
        b.scale_signature, provenance="declared_same_pass", source_provenance="declared_source",
    ))
    result = CurrentVisualPriceComparator().compare(a, b)
    assert result.entry_validity.state is MeasurementValidity.UNDETERMINED
    assert result.entry_validity.reasons == ("PROVENANCE_UNVERIFIED",)
    assert result.accredited_delta is None


@pytest.mark.parametrize("missing", (
    "signature_reference", "extraction_version", "effective_configuration",
    "source_provenance", "parent_coordinate_system",
))
def test_missing_signature_information_abstains(missing):
    a, b = _context(), _context(2)
    a = replace(a, scale_signature=replace(a.scale_signature, **{missing: None}))
    result = CurrentVisualPriceComparator().compare(a, b)
    assert result.entry_validity.state is MeasurementValidity.UNDETERMINED
    assert result.compatibility is VisualPriceCompatibility.UNDETERMINED
    assert result.accredited_delta is None


def test_unknown_source_is_not_filled_from_extractor_source():
    a = _context()
    a = replace(a, source_key=None, scale_signature=replace(
        a.scale_signature, identity=replace(a.scale_signature.identity, source_key=None),
    ))
    result = CurrentVisualPriceComparator().compare(a, _context(2))
    assert result.entry_validity.state is MeasurementValidity.UNDETERMINED
    assert result.accredited_delta is None


def test_different_method_versions_without_equivalence_do_not_prove_incompatibility():
    a, b = _context(), _context(2)
    b = replace(b, scale_signature=replace(b.scale_signature, extraction_version="fixture-v2"))
    result = CurrentVisualPriceComparator().compare(a, b)
    assert result.compatibility is VisualPriceCompatibility.UNDETERMINED


def test_changed_geometry_without_a_transform_remains_undetermined():
    a, b = _context(), _context(2)
    shifted = ChartRegion(3, 7, 16, 20)
    b = replace(b, chart_region=shifted, price_observation_region=shifted,
                scale_signature=replace(b.scale_signature, chart_region=shifted, price_region=shifted))
    assert CurrentVisualPriceComparator().compare(a, b).compatibility is VisualPriceCompatibility.UNDETERMINED


def test_claimed_verified_reference_does_not_authenticate_itself():
    a, b = _context(), _context(2)
    result = CurrentVisualPriceComparator().compare(a, b, relation_evidence=_relation(a, b))
    assert result.compatibility is VisualPriceCompatibility.UNDETERMINED
    assert result.verification_references == ()
    assert result.accredited_delta is None


def test_applicable_verified_fixture_relation_is_only_test_scope():
    a, b = _context(), _context(2, 4.0)
    relation = _relation(a, b)
    result = _synthetic_comparator(a, b, relation).compare(a, b, relation_evidence=relation)
    assert result.entry_validity.state is MeasurementValidity.VALID
    assert result.exit_validity.state is MeasurementValidity.VALID
    assert result.compatibility is VisualPriceCompatibility.COMPATIBLE
    assert result.evidence_scope is EvidenceScope.TEST_ONLY
    assert result.accredited_delta is None
    assert not result.has_accredited_comparison
    assert VisualPriceMovementClassifier().classify(result).movement is PriceMovement.UNRESOLVED
    assert VisualPriceMovementClassifier(1).classify(result).movement is PriceMovement.UNRESOLVED


def test_fixture_cannot_be_promoted_by_relabeling_the_relation_scope():
    a, b = _context(), _context(2)
    relation = replace(_relation(a, b), scope=EvidenceScope.PRODUCTION)
    result = CurrentVisualPriceComparator(_FixtureVerifier(a, b, relation)).compare(
        a, b, relation_evidence=relation,
    )
    assert result.compatibility is VisualPriceCompatibility.UNDETERMINED
    assert result.accredited_delta is None


def test_verified_relational_contradiction_is_not_missing_evidence():
    a, b = _context(), _context(2)
    relation = _relation(a, b)
    result = _synthetic_comparator(a, b, relation, contradiction=True).compare(
        a, b, relation_evidence=relation,
    )
    assert result.compatibility is VisualPriceCompatibility.INCOMPATIBLE
    assert result.accredited_delta is None


def test_incomplete_verified_claims_do_not_establish_common_basis():
    a, b = _context(), _context(2)
    relation = _relation(a, b)
    result = _synthetic_comparator(a, b, relation, claims=("scale_continuity",)).compare(
        a, b, relation_evidence=relation,
    )
    assert result.compatibility is VisualPriceCompatibility.UNDETERMINED


def test_mismatched_verifier_receipt_is_rejected(monkeypatch):
    a, b = _context(), _context(2)
    relation = _relation(a, b)
    verifier = _FixtureVerifier(a, b, relation)
    valid_verify = verifier.verify_relation

    def wrong_receipt(evidence, entry, exit):
        return replace(valid_verify(evidence, entry, exit), signature_references=("wrong", "wrong"))

    monkeypatch.setattr(verifier, "verify_relation", wrong_receipt)
    result = CurrentVisualPriceComparator(verifier, evidence_scope=EvidenceScope.TEST_ONLY).compare(
        a, b, relation_evidence=relation,
    )
    assert result.compatibility is VisualPriceCompatibility.UNDETERMINED
    assert result.compatibility_reasons == ("RELATIONAL_RECEIPT_UNBOUND",)


def test_verifier_failure_abstains_without_publishing_a_delta(monkeypatch):
    a, b = _context(), _context(2)
    relation = _relation(a, b)
    verifier = _FixtureVerifier(a, b, relation)

    def unavailable(*args, **kwargs):
        raise OSError("synthetic verifier unavailable")

    monkeypatch.setattr(verifier, "verify_relation", unavailable)
    result = CurrentVisualPriceComparator(verifier, evidence_scope=EvidenceScope.TEST_ONLY).compare(
        a, b, relation_evidence=relation,
    )
    assert result.compatibility is VisualPriceCompatibility.UNDETERMINED
    assert result.accredited_delta is None


@pytest.mark.parametrize("y", (0.0, 19.0))
def test_affine_breakouts_are_not_clamped(y):
    a, b = _context(), _context(2, y)
    relation = _relation(a, b)
    result = _synthetic_comparator(a, b, relation).compare(a, b, relation_evidence=relation)
    assert result.compatibility is VisualPriceCompatibility.COMPATIBLE
    assert result.exit_anchored_value == (18 - y) / 16
    assert result.exit_anchored_value > 1 or result.exit_anchored_value < 0
    assert result.accredited_delta is None


def test_evidence_for_another_measurement_is_not_a_verified_contradiction():
    a, b = _context(), _context(2)
    registered = _relation(a, b)
    wrong = replace(registered, exit_signature_reference="another-signature")
    result = _synthetic_comparator(a, b, registered).compare(a, b, relation_evidence=wrong)
    assert result.compatibility is VisualPriceCompatibility.UNDETERMINED
    assert result.accredited_delta is None


def test_invalid_normalization_is_separate_from_legacy_geometry():
    a = _context()
    a = replace(a, current_visual_price=replace(
        a.current_visual_price, price=replace(a.current_visual_price.price, normalized_roi_y=0.123),
    ))
    result = CurrentVisualPriceComparator().compare(a, _context(2))
    assert result.entry_validity.state is MeasurementValidity.INVALID
    assert result.status is CurrentVisualPriceComparisonStatus.AVAILABLE
    assert result.accredited_delta is None


def test_failed_extraction_never_produces_a_usable_delta():
    a = replace(_context(), current_visual_price=CurrentVisualPriceExtraction(
        None, CurrentVisualPriceStatus.AMBIGUOUS_VISUAL_PRICE,
        diagnostic="fixture-ambiguous",
    ))
    result = CurrentVisualPriceComparator().compare(a, _context(2))
    assert result.entry_validity.state is MeasurementValidity.INVALID
    assert result.delta is result.accredited_delta is None


def test_legacy_outcome_stays_independent_of_unverified_marker_comparison():
    a, b = _context(), _context(2)
    entry = a.reference_result.reference
    exit = replace(entry, value=entry.value + 0.1)
    assert StrategyObservationOutcomeResolver.compare(
        SignalDirection.CALL, entry, exit,
    ) is StrategyObservationOutcome.WIN
    assert CurrentVisualPriceComparator().compare(a, b).compatibility is VisualPriceCompatibility.UNDETERMINED
