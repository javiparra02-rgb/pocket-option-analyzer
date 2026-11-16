from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from pocket_option_analyzer.vision.models import (
    ChartRegion,
    CurrentVisualPriceExtraction,
)

from .visual_price_reference_result import VisualPriceReferenceResult
from .visual_scale_signature import VisualScaleSignature


@dataclass(frozen=True, slots=True)
class CurrentVisualPriceComparisonContext:
    """Immutable visual-price evidence captured from one analyzed frame."""

    current_visual_price: CurrentVisualPriceExtraction | None

    chart_region: ChartRegion | None

    price_observation_region: ChartRegion | None

    reference_result: VisualPriceReferenceResult

    # Traceability only: these fields must not change legacy context equality
    # or act as evidence of scale comparability. Unknown values stay absent.
    frame_id: int | None = field(default=None, kw_only=True, compare=False)
    frame_timestamp: datetime | None = field(
        default=None, kw_only=True, compare=False,
    )
    timestamp_origin: str | None = field(default=None, kw_only=True, compare=False)
    monotonic_timestamp: float | None = field(
        default=None, kw_only=True, compare=False,
    )
    source_key: str | None = field(default=None, kw_only=True, compare=False)
    session_key: str | None = field(default=None, kw_only=True, compare=False)
    execution_id: str | None = field(default=None, kw_only=True, compare=False)
    # Analysis routing label, not an acquisition source or extractor identity.
    analysis_source: str | None = field(default=None, kw_only=True, compare=False)
    scale_signature: VisualScaleSignature | None = field(
        default=None, kw_only=True, compare=False,
    )
    # I3: bound to the existing same-pass evaluation after analysis. This is
    # local provenance, not acquisition, instrument or scale accreditation.
    evaluation_id: str | None = field(default=None, kw_only=True, compare=False)
