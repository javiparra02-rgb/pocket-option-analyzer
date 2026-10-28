"""Explicit offline entry; ordinary methods always preserve legacy v1."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from math import ceil
from typing import Any

import cv2
import numpy as np

from pocket_option_analyzer.vision.models.composite_guide import (
    CONTRACT,
    CompositeGuideTrace,
)
from pocket_option_analyzer.vision.models.current_visual_price_detection_trace import (
    CurrentVisualPriceAnalysis,
)
from pocket_option_analyzer.vision.models.current_visual_price_extraction import (
    CurrentVisualPriceExtraction,
)
from pocket_option_analyzer.vision.models.current_visual_price_search import (
    CurrentVisualPriceSearchConstraints,
    CurrentVisualPriceSearchPlan,
)
from pocket_option_analyzer.vision.preprocessing import FrameValidator

from .composite_guide_support import CompositeGuideSupportObserver
from .pocket_option_current_price_mask_builder import (
    PocketOptionCurrentPriceMaskBuilder,
)
from .pocket_option_current_visual_price_extractor import (
    PocketOptionCurrentVisualPriceExtractor,
)
from .pocket_option_current_visual_price_search_window_resolver import (
    PocketOptionCurrentVisualPriceSearchWindowResolver,
)


@dataclass(frozen=True, slots=True)
class OfflineCompositeGuideEvaluation:
    analysis: CurrentVisualPriceAnalysis
    plan: CurrentVisualPriceSearchPlan
    support: CompositeGuideTrace
    mode: str = "LEGACY_V2_OFFLINE_EXPERIMENTAL"

    def to_dict(self) -> dict[str, Any]:
        """JSON-compatible standalone envelope, not a historical recorder record."""
        return dict(json.loads(json.dumps(asdict(self), allow_nan=False)))


class CompositeGuidePriceExtractor:
    """Does not replace or enable the live extractor, even when enabled=True."""

    def __init__(self, *, enabled: bool = False, min_confidence: float = 0.60) -> None:
        if not isinstance(enabled, bool):
            raise TypeError("enabled must be bool")
        self._enabled = enabled
        self._legacy = PocketOptionCurrentVisualPriceExtractor(
            min_confidence=min_confidence
        )
        self._offline = PocketOptionCurrentVisualPriceExtractor(
            min_confidence=min_confidence, source=CONTRACT
        )

    def extract(self, image: np.ndarray) -> CurrentVisualPriceExtraction:
        return self._legacy.extract(image)

    def extract_with_trace(self, image: np.ndarray) -> CurrentVisualPriceAnalysis:
        return self._legacy.extract_with_trace(image)

    def evaluate_offline(
        self,
        image: np.ndarray,
        *,
        roi_origin: tuple[int, int] = (0, 0),
    ) -> OfflineCompositeGuideEvaluation:
        if not self._enabled:
            raise ValueError("v2 requires explicit offline activation")
        if not FrameValidator.validate(image):
            raise ValueError("invalid original BGR/BGRA raster")
        if len(roi_origin) != 2 or any(type(v) is not int or v < 0 for v in roi_origin):
            raise ValueError("ROI origin must contain two nonnegative integers")
        height, width = image.shape[:2]
        if height * width > 4_000_000:
            raise ValueError("offline raster budget exceeded; no partial evaluation")
        bgr = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR) if image.shape[2] == 4 else image
        direct = PocketOptionCurrentPriceMaskBuilder().build(bgr)
        guide, support = CompositeGuideSupportObserver().observe(
            bgr, direct, roi_origin=roi_origin
        )
        if support.rejection_reasons:
            raise ValueError("incomplete composite census; no partial evaluation")
        constraints = CurrentVisualPriceSearchConstraints(
            image_width=width,
            image_height=height,
            right_band_ratio=0.2,
            max_line_gap_ratio=0.01,
            max_line_start_offset_ratio=0.05,
            min_line_run_ratio=0.7,
            label_zone_ratio=0.25,
            label_vertical_radius_ratio=0.025,
            max_row_gap_px=1,
            max_candidate_height_px=7,
        )
        resolver = PocketOptionCurrentVisualPriceSearchWindowResolver()
        plan = resolver.resolve_with_guide_support(
            mask=direct,
            guide_mask=guide,
            constraints=constraints,
        )
        analysis = self._offline._extract_dynamic(
            mask=direct,
            guide_mask=guide,
            plan=plan,
            image_width=width,
            image_height=height,
            masked_pixel_count=int(np.count_nonzero(direct)),
            safe_top=max(ceil(height * 0.05), 12),
            safe_bottom=max(ceil(height * 0.05), 12),
            qualification_contract=CONTRACT,
        )
        return OfflineCompositeGuideEvaluation(
            analysis=analysis, plan=plan, support=support
        )
