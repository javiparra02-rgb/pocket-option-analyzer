"""Descriptive scale contracts, not a scale certifier or a trading interface.

No production verifier is supplied. References and claimed states are data,
not authentication. TEST_ONLY assessments cannot authorize production use.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from pocket_option_analyzer.vision.models.chart_region import ChartRegion


class MeasurementValidity(StrEnum):
    VALID = "VALID"
    INVALID = "INVALID"
    UNDETERMINED = "UNDETERMINED"


class VisualPriceCompatibility(StrEnum):
    COMPATIBLE = "COMPATIBLE"
    INCOMPATIBLE = "INCOMPATIBLE"
    UNDETERMINED = "UNDETERMINED"


class EvidenceScope(StrEnum):
    PRODUCTION = "PRODUCTION"
    TEST_ONLY = "TEST_ONLY"


class EvidenceVerification(StrEnum):
    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"
    CONTRADICTED = "CONTRADICTED"


class NoiseCalibrationState(StrEnum):
    UNCALIBRATED = "UNCALIBRATED"
    UNVERIFIED = "UNVERIFIED"


@dataclass(frozen=True, slots=True)
class VisualMeasurementIdentity:
    execution_id: str | None = None
    session_key: str | None = None
    source_key: str | None = None
    frame_id: int | None = None

    def __post_init__(self) -> None:
        for value in (self.execution_id, self.session_key, self.source_key):
            if value is not None and type(value) is not str:
                raise ValueError("Identity fields must be text or absent")
        if self.frame_id is not None and type(self.frame_id) is not int:
            raise ValueError("Frame identity must be an integer or absent")

    @property
    def is_complete(self) -> bool:
        return (
            all(isinstance(v, str) and bool(v.strip()) for v in (
                self.execution_id, self.session_key, self.source_key,
            ))
            and type(self.frame_id) is int and self.frame_id > 0
        )


@dataclass(frozen=True, slots=True)
class VisualScaleSignature:
    schema_version: int = 1
    signature_reference: str | None = None
    identity: VisualMeasurementIdentity = VisualMeasurementIdentity()
    coordinate_system: str = "PRICE_OBSERVATION_ROI_LOCAL_PIXELS"
    normalization: str = "ONE_MINUS_Y_OVER_HEIGHT_MINUS_ONE"
    extraction_method: str | None = None
    extraction_version: str | None = None
    extraction_source: str | None = None
    # Explicit primitive snapshot only; never inspect extractor private state.
    effective_configuration: tuple[
        tuple[str, str | int | float | bool | None], ...
    ] | None = None
    provenance: str | None = None
    source_provenance: str | None = None
    instrument_identity: str | None = None
    price_region: ChartRegion | None = None
    chart_region: ChartRegion | None = None
    parent_coordinate_system: str | None = None
    anchors: tuple[tuple[str, float, float, float, float], ...] = ()
    anchor_top_roi_y: int | None = None
    anchor_bottom_roi_y: int | None = None
    anchor_provenance: str | None = None
    anchor_identities: tuple[str, ...] = ()
    scale_continuity_reference: str | None = None
    noise_calibration_state: NoiseCalibrationState = (
        NoiseCalibrationState.UNCALIBRATED
    )
    evidence_references: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("Unsupported visual scale signature schema")
        if not isinstance(self.identity, VisualMeasurementIdentity):
            raise ValueError("Signature identity must be immutable")
        for value in (
            self.signature_reference, self.coordinate_system, self.normalization,
            self.extraction_method, self.extraction_version, self.extraction_source,
            self.provenance, self.source_provenance, self.instrument_identity,
            self.parent_coordinate_system, self.anchor_provenance,
            self.scale_continuity_reference,
        ):
            if value is not None and type(value) is not str:
                raise ValueError("Signature descriptions must be text or absent")
        for value in (self.anchor_top_roi_y, self.anchor_bottom_roi_y):
            if value is not None and (type(value) not in (int, float) or not isfinite(value)):
                raise ValueError("Anchor coordinates must be finite or absent")
        for region in (self.price_region, self.chart_region):
            if region is not None and not isinstance(region, ChartRegion):
                raise ValueError("Signature regions must be ChartRegion values")
        if not isinstance(self.noise_calibration_state, NoiseCalibrationState):
            raise ValueError("Invalid noise calibration state")
        for values in (self.anchor_identities, self.evidence_references):
            if type(values) is not tuple or any(type(v) is not str for v in values):
                raise ValueError("Signature references must be immutable text tuples")
        if type(self.anchors) is not tuple:
            raise ValueError("Anchors must be an immutable tuple")
        for anchor in self.anchors:
            if (
                type(anchor) is not tuple or len(anchor) != 5
                or type(anchor[0]) is not str
                or any(type(v) not in (int, float) or not isfinite(v)
                       for v in anchor[1:])
            ):
                raise ValueError("Invalid descriptive anchor")
        if self.effective_configuration is not None:
            if type(self.effective_configuration) is not tuple:
                raise ValueError("Configuration must be an immutable tuple")
            keys = set()
            for item in self.effective_configuration:
                if (
                    type(item) is not tuple or len(item) != 2
                    or type(item[0]) is not str or item[0] in keys
                    or type(item[1]) not in (str, int, float, bool, type(None))
                    or (type(item[1]) is float and not isfinite(item[1]))
                ):
                    raise ValueError("Invalid effective configuration snapshot")
                keys.add(item[0])


@dataclass(frozen=True, slots=True)
class MeasurementValidityResult:
    state: MeasurementValidity = MeasurementValidity.UNDETERMINED
    reasons: tuple[str, ...] = ("MEASUREMENT_NOT_VERIFIED",)
    evidence_references: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.state, MeasurementValidity):
            raise ValueError("Invalid measurement validity state")
        for values in (self.reasons, self.evidence_references):
            if type(values) is not tuple or any(type(v) is not str for v in values):
                raise ValueError("Validity diagnostics must be immutable")
        if self.state is MeasurementValidity.VALID and (
            self.reasons or not self.evidence_references
        ):
            raise ValueError("VALID requires verified provenance references")


@dataclass(frozen=True, slots=True)
class VisualScaleRelationEvidence:
    entry_identity: VisualMeasurementIdentity
    exit_identity: VisualMeasurementIdentity
    entry_signature_reference: str
    exit_signature_reference: str
    evidence_reference: str
    provenance: str
    scope: EvidenceScope
    schema_version: int = 1
    relation_type: str = "SAME_ANCHOR_AFFINE_V1"
    claimed_verification: EvidenceVerification = EvidenceVerification.UNVERIFIED

    def __post_init__(self) -> None:
        if (
            not isinstance(self.entry_identity, VisualMeasurementIdentity)
            or not isinstance(self.exit_identity, VisualMeasurementIdentity)
            or not isinstance(self.scope, EvidenceScope)
            or not isinstance(self.claimed_verification, EvidenceVerification)
            or type(self.schema_version) is not int or self.schema_version != 1
        ):
            raise ValueError("Invalid relational evidence schema")
        for value in (
            self.entry_signature_reference, self.exit_signature_reference,
            self.evidence_reference, self.provenance, self.relation_type,
        ):
            if type(value) is not str or not value.strip():
                raise ValueError("Relational evidence requires explicit references")


@dataclass(frozen=True, slots=True)
class ScaleEvidenceAssessment:
    """Receipt from a trusted verifier, not an independently authentic token.

    verify_* must authenticate the actual supplied signatures/evidence, including
    identities, configuration and scope, not merely compare reference strings.
    """

    status: EvidenceVerification
    scope: EvidenceScope
    identities: tuple[VisualMeasurementIdentity, ...]
    signature_references: tuple[str, ...]
    evidence_reference: str
    covered_claims: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.status, EvidenceVerification) or not isinstance(self.scope, EvidenceScope):
            raise ValueError("Invalid assessment status or scope")
        if type(self.identities) is not tuple or any(
            not isinstance(v, VisualMeasurementIdentity) for v in self.identities
        ):
            raise ValueError("Assessment identities must be immutable")
        for values in (self.signature_references, self.covered_claims):
            if type(values) is not tuple or any(type(v) is not str for v in values):
                raise ValueError("Assessment references must be immutable")
        if type(self.evidence_reference) is not str:
            raise ValueError("Assessment receipt identity must be text")


RELATION_CLAIMS = frozenset({
    "source_and_instrument", "method_equivalence", "coordinate_mapping",
    "anchor_correspondence", "scale_continuity",
})


class VisualScaleEvidenceVerifier(ABC):
    """Blocking integration boundary. No real verifier is implemented in I2.

    Implementations must be independently reviewed/trusted. A permissive mock
    is NOT a production certifier. The factory never injects one by default.
    """

    @property
    @abstractmethod
    def scope(self) -> EvidenceScope:
        raise NotImplementedError("Scale evidence verifier unavailable")

    @abstractmethod
    def verify_measurement(
        self, signature: VisualScaleSignature,
        *, roi_y: float, normalized_roi_y: float,
    ) -> ScaleEvidenceAssessment:
        """Authenticate this measured position, its frame and configuration.

        Authentication must cover the actual supplied values and signature,
        not merely their textual references or a claimed VERIFIED state.
        """
        raise NotImplementedError("Measurement provenance verifier unavailable")

    @abstractmethod
    def verify_relation(
        self, evidence: VisualScaleRelationEvidence,
        entry: VisualScaleSignature, exit: VisualScaleSignature,
    ) -> ScaleEvidenceAssessment:
        """Authenticate the relation and its stated common affine basis."""
        raise NotImplementedError("Relational scale verifier unavailable")
