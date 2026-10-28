"""Separate observational evidence for the offline legacy v2 contract."""

from __future__ import annotations

from dataclasses import dataclass

CONTRACT = "dynamic_guide_label_v2"
Span = tuple[int, int, int]  # ROI row, start_x, end_x (half-open)
Color = tuple[int, int, int]  # original BGR, not inferred foreground


@dataclass(frozen=True, slots=True)
class CompositeRowEvidence:
    row_y: int
    direct_bgr: Color
    anchor_background_bgr: Color
    observed_bgr: tuple[Color, ...]
    background_bgr: tuple[Color, ...]
    beta_min: float | None
    beta_max: float | None
    maximum_residual: float | None


@dataclass(frozen=True, slots=True)
class CompositeRegionEvidence:
    top: int
    bottom: int
    start_x: int
    end_x: int
    left_anchor: tuple[int, int]
    right_anchor: tuple[int, int]
    rows: tuple[CompositeRowEvidence, ...]
    rejection_reasons: tuple[str, ...]
    direct_seed_bounds: tuple[tuple[int, int], ...] = ()

    @property
    def accepted(self) -> bool:
        return not self.rejection_reasons


@dataclass(frozen=True, slots=True)
class CompositeGuideTrace:
    raster_sha256: str
    config_sha256: str
    image_width: int
    image_height: int
    roi_origin: tuple[int, int]
    direct_spans: tuple[Span, ...]
    composite_spans: tuple[Span, ...]
    regions: tuple[CompositeRegionEvidence, ...]
    rejection_reasons: tuple[str, ...] = ()
    contract_version: str = CONTRACT
    coordinate_system: str = "original_png_roi_half_open; frame=roi+origin"
    provenance: str = "original_BGR_raster; nonrecursive_direct_anchors"
    confidence_kind: str = "photometric_compatibility_not_semantic_probability"
