from __future__ import annotations

from dataclasses import dataclass

from pocket_option_analyzer.vision.models import (
    ChartRegion,
    CurrentVisualPriceExtraction,
)

from .visual_price_reference_result import VisualPriceReferenceResult


@dataclass(frozen=True, slots=True)
class CurrentVisualPriceComparisonContext:
    """Immutable visual-price evidence captured from one analyzed frame."""

    current_visual_price: CurrentVisualPriceExtraction | None

    chart_region: ChartRegion | None

    price_observation_region: ChartRegion | None

    reference_result: VisualPriceReferenceResult
