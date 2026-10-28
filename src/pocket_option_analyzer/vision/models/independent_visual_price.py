"""Typed, ROI-local H1/H2 evidence. No trading or monetary-price semantics."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

H1_SOURCE = "fbebf36ea2e428e191d3a7037266ae5d607b4e00cfb1bdb300b95979141011f8"
H2_SOURCE = "155b6e411ce60ffc0e9b43768281e22cb9d0021470f06936ab327e69faf81755"
IDENTITY_CONTRACT = "independent_h1_h2_r3d_v1"


@dataclass(frozen=True, slots=True)
class PixelBox:
    """Half-open pixel envelope; never silently clipped."""

    x0: int
    y0: int
    x1: int
    y1: int

    def __post_init__(self) -> None:
        if any(type(v) is not int for v in self.coordinates):
            raise ValueError("PixelBox requires integer coordinates")
        if self.x1 <= self.x0 or self.y1 <= self.y0:
            raise ValueError("PixelBox requires positive area")

    @property
    def coordinates(self) -> tuple[int, int, int, int]:
        return self.x0, self.y0, self.x1, self.y1

    @property
    def area(self) -> int:
        return (self.x1 - self.x0) * (self.y1 - self.y0)

    def contains(self, other: PixelBox) -> bool:
        return (
            self.x0 <= other.x0
            and other.x1 <= self.x1
            and self.y0 <= other.y0
            and other.y1 <= self.y1
        )


@dataclass(frozen=True, slots=True)
class ObservationGeometry:
    """Observation ROI origin in the parent frame; not a semantic chart claim."""

    frame_x: int
    frame_y: int
    width: int
    height: int

    def __post_init__(self) -> None:
        values = (self.frame_x, self.frame_y, self.width, self.height)
        if any(type(v) is not int for v in values):
            raise ValueError("Observation geometry requires integers")
        if min(self.frame_x, self.frame_y) < 0 or min(self.width, self.height) < 1:
            raise ValueError("Invalid observation geometry")

    def to_frame(self, box: PixelBox) -> PixelBox:
        return PixelBox(
            box.x0 + self.frame_x,
            box.y0 + self.frame_y,
            box.x1 + self.frame_x,
            box.y1 + self.frame_y,
        )

    def to_roi(self, box: PixelBox) -> PixelBox:
        return PixelBox(
            box.x0 - self.frame_x,
            box.y0 - self.frame_y,
            box.x1 - self.frame_x,
            box.y1 - self.frame_y,
        )


@dataclass(frozen=True, slots=True)
class OcrWord:
    text: str
    box: PixelBox

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not isinstance(self.box, PixelBox):
            raise ValueError("Invalid OCR word")


@dataclass(frozen=True, slots=True)
class OcrReading:
    words: tuple[OcrWord, ...]
    backend: str
    text_angle: float = 0.0

    def __post_init__(self) -> None:
        if (
            not isinstance(self.backend, str)
            or not self.backend
            or not isfinite(self.text_angle)
        ):
            raise ValueError("Invalid OCR provenance")
        if not isinstance(self.words, tuple) or any(
            not isinstance(w, OcrWord) for w in self.words
        ):
            raise ValueError("Invalid OCR word sequence")
        if abs(self.text_angle) > 10:
            raise ValueError("OCR_ROTATION_OUTSIDE_DOMAIN")


class ScaleContextState(StrEnum):
    AVAILABLE = "CONTEXT_AVAILABLE"
    INSUFFICIENT = "CONTEXT_INSUFFICIENT"
    AMBIGUOUS = "CONTEXT_AMBIGUOUS"
    INVALID = "CONTEXT_INVALID_INPUT"


@dataclass(frozen=True, slots=True)
class GridEvidence:
    row: int
    x0: int
    x1: int
    supported_pixels: int


@dataclass(frozen=True, slots=True)
class ScaleTick:
    text: str
    value: str
    box: PixelBox
    grid: GridEvidence


@dataclass(frozen=True, slots=True)
class ScaleContext:
    state: ScaleContextState
    reasons: tuple[str, ...]
    geometry: ObservationGeometry
    image_sha256: str
    backend: str
    scale_region: PixelBox | None = None
    observed_grid: PixelBox | None = None
    ticks: tuple[ScaleTick, ...] = ()
    alignment_spread: int | None = None
    linear_residual: float | None = None
    panel_delta: float | None = None
    rejected_ticks: tuple[str, ...] = ()
    text_angle: float = 0.0
    full_chart_extent_certified: bool = False
    contract_version: str = "independent_scale_context_v1"
    source_aggregate: str = H1_SOURCE

    def __post_init__(self) -> None:
        if self.full_chart_extent_certified:
            raise ValueError("H1 authorizes observed grid only")
        if self.state is ScaleContextState.AVAILABLE:
            if len(self.image_sha256) != 64 or any(
                c not in "0123456789abcdef" for c in self.image_sha256
            ):
                raise ValueError("Available H1 requires binding to original BGR pixels")
            if (
                self.scale_region is None
                or self.observed_grid is None
                or len(self.ticks) < 3
            ):
                raise ValueError(
                    "Available scale requires regions and grid-bound ticks"
                )
            image = PixelBox(0, 0, self.geometry.width, self.geometry.height)
            if not image.contains(self.scale_region) or not image.contains(
                self.observed_grid
            ):
                raise ValueError("H1 regions exceed image")


class LabelRoleState(StrEnum):
    VERIFIED = "ROLE_VERIFIED"
    INSUFFICIENT = "ROLE_INSUFFICIENT"
    AMBIGUOUS = "ROLE_AMBIGUOUS"
    NO_PROPOSAL = "ROLE_NO_PROPOSAL"
    REJECTED = "ROLE_REJECTED"
    INVALID = "ROLE_INVALID_CONTEXT"
    BUDGET = "ROLE_BUDGET_EXCEEDED"


@dataclass(frozen=True, slots=True)
class LabelProposal:
    box: PixelBox
    fill_pixels: int
    fill_color_bgr: tuple[float, float, float]
    glyph_pixels: int
    original_fill_components: int
    sources: tuple[tuple[int, int], ...]


@dataclass(frozen=True, slots=True)
class ExternalGuide:
    row: int
    x0: int
    x1: int
    accepted: bool
    reason: str
    gap_to_body: int


@dataclass(frozen=True, slots=True)
class LabelRoleCandidate:
    proposal: LabelProposal
    state: LabelRoleState
    reason: str
    relevant: bool
    guides: tuple[ExternalGuide, ...] = ()
    favorable: tuple[str, ...] = ()
    contradictions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LabelRoleResult:
    state: LabelRoleState
    reason: str
    proposals: tuple[LabelProposal, ...] = ()
    candidates: tuple[LabelRoleCandidate, ...] = ()
    selected_box: PixelBox | None = None
    proposal_rejections: tuple[tuple[str, int], ...] = ()

    def __post_init__(self) -> None:
        if (self.selected_box is not None) != (self.state is LabelRoleState.VERIFIED):
            raise ValueError("Only verified identity selects a box")
        if self.selected_box is not None:
            verified = [
                c for c in self.candidates if c.state is LabelRoleState.VERIFIED
            ]
            if len(verified) != 1 or verified[0].proposal.box != self.selected_box:
                raise ValueError("Selection needs a unique accredited candidate")
            if any(
                c.relevant and c.state is LabelRoleState.INSUFFICIENT
                for c in self.candidates
            ):
                raise ValueError("Unresolved competitor prevents selection")


@dataclass(frozen=True, slots=True)
class IndependentPriceTrace:
    context: ScaleContext
    role: LabelRoleResult
    quality: float | None
    quality_threshold: float
    config_sha256: str
    contract_version: str = IDENTITY_CONTRACT
    h2_source_manifest: str = H2_SOURCE
    execution_scope: str = "EXPLICIT_OFFLINE_ONLY"
    absence_certified: bool = False
    legacy_row_metrics_applicable: bool = False

    def __post_init__(self) -> None:
        if self.absence_certified or self.legacy_row_metrics_applicable:
            raise ValueError("H1/H2 does not certify absence or legacy row metrics")
        if self.quality is not None and (
            self.role.state is not LabelRoleState.VERIFIED
            or not isfinite(self.quality)
            or not 0 <= self.quality <= 1
        ):
            raise ValueError("Quality is only meaningful after unique identity")
