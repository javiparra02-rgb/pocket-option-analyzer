"""Conservative, explicitly offline configuration; no live settings binding."""

from dataclasses import dataclass, fields
from math import isfinite


@dataclass(frozen=True, slots=True)
class ScaleContextConfig:
    min_ticks: int = 3
    max_pixels: int = 4_000_000
    max_words: int = 400
    max_numeric_candidates: int = 80
    max_groups: int = 12
    ocr_timeout_seconds: float = 15.0
    max_seconds: float = 20.0
    alignment_tolerance_px: int = 6
    grid_min_run_width_ratio: float = 0.18
    grid_short_run_width_ratio: float = 0.04
    grid_delta: float = 2.0
    grid_max_chroma: float = 60.0
    tick_background_max_chroma: float = 40.0
    panel_min_median_delta: float = 4.0
    linear_residual_ratio: float = 0.03
    group_boundary_tolerance_px: int = 4

    def __post_init__(self) -> None:
        _positive_parameters(self)
        if self.min_ticks < 3:
            raise ValueError("Independent scale requires at least three ticks")
        if (
            not 0
            < self.grid_short_run_width_ratio
            <= self.grid_min_run_width_ratio
            <= 1
        ):
            raise ValueError("Invalid grid run ratios")


@dataclass(frozen=True, slots=True)
class LabelRoleConfig:
    max_pixels: int = 4_000_000
    max_colors: int = 96
    min_color_pixels: int = 80
    max_proposals: int = 64
    max_associations: int = 64
    max_seconds: float = 4.0
    quantization: int = 16
    min_width: int = 20
    max_width: int = 180
    min_height: int = 10
    max_height: int = 44
    min_ratio: float = 1.6
    max_ratio: float = 14.0
    min_fill: float = 0.28
    min_glyph_pixels: int = 5
    dedup_iou: float = 0.65
    dock_tolerance: int = 6
    min_scale_overlap: float = 0.6
    min_guide_run: int = 24
    guide_color_distance: float = 38.0
    guide_neighbor_contrast: float = 6.0
    guide_center_tolerance: int = 3

    def __post_init__(self) -> None:
        _positive_parameters(self)
        if 256 % self.quantization or self.quantization > 128:
            raise ValueError("Quantization must divide 256")
        if self.min_width > self.max_width or self.min_height > self.max_height:
            raise ValueError("Invalid proposal geometry limits")
        if self.min_ratio > self.max_ratio:
            raise ValueError("Invalid aspect ratio limits")
        if any(
            not 0 < x <= 1
            for x in (self.min_fill, self.dedup_iou, self.min_scale_overlap)
        ):
            raise ValueError("Invalid role ratios")


def _positive_parameters(config: ScaleContextConfig | LabelRoleConfig) -> None:
    for field in fields(config):
        value = getattr(config, field.name)
        if isinstance(value, bool) or not isinstance(value, (float, int)):
            raise ValueError(f"Invalid {field.name}")
        if not isfinite(value) or value <= 0:
            raise ValueError(f"Invalid {field.name}")
        if field.type is int and type(value) is not int:
            raise ValueError(f"{field.name} must be integer")


@dataclass(frozen=True, slots=True)
class IndependentPriceConfig:
    enabled: bool = False
    min_quality: float = 0.60
    scale: ScaleContextConfig = ScaleContextConfig()
    role: LabelRoleConfig = LabelRoleConfig()

    def __post_init__(self) -> None:
        if type(self.enabled) is not bool:
            raise ValueError("enabled must be an explicit boolean")
        if not isfinite(self.min_quality) or not 0 <= self.min_quality <= 1:
            raise ValueError("Invalid quality threshold")
