from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

import numpy as np

from pocket_option_analyzer.application.strategy.visual_price_reference_result import (
    VisualPriceReferenceResult,
)
from pocket_option_analyzer.vision.models import (
    CandleDetectionTrace,
    ChartRegion,
    CurrentVisualPriceDetectionTrace,
    CurrentVisualPriceExtraction,
    MarketAnalysis,
)


class VisualEvidencePhase(StrEnum):
    """Lifecycle phase that associates a frame with a strategy snapshot."""

    ENTRY = "entry"
    EXIT = "exit"


@dataclass(frozen=True, slots=True)
class VisualEvidenceAssociation:
    """Immutable link between one snapshot and one analyzed frame."""

    snapshot_id: str
    phase: VisualEvidencePhase
    observed_at: datetime
    resolve_at: datetime
    candle_interval_started_at: datetime | None = None
    resolved_at: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.phase, VisualEvidencePhase):
            raise TypeError("phase must be a VisualEvidencePhase.")
        if not self.snapshot_id.strip():
            raise ValueError("snapshot_id cannot be empty.")
        for field_name in ("observed_at", "resolve_at"):
            _normalize_utc(self, field_name)
        if self.candle_interval_started_at is not None:
            _normalize_utc(self, "candle_interval_started_at")
            if self.snapshot_id != self.candle_interval_started_at.isoformat():
                raise ValueError(
                    "snapshot_id must match candle_interval_started_at."
                )
        if self.phase is VisualEvidencePhase.ENTRY:
            if self.candle_interval_started_at is None:
                raise ValueError(
                    "Entry evidence requires candle_interval_started_at."
                )
            if self.resolved_at is not None:
                raise ValueError("Entry evidence cannot include resolved_at.")
            return
        if self.resolved_at is None:
            raise ValueError("Exit evidence requires resolved_at.")
        _normalize_utc(self, "resolved_at")


@dataclass(slots=True)
class VisualFrameEvidence:
    """In-memory evidence produced by exactly one analyzed capture.

    Image arrays are borrowed references. They are deliberately not copied and
    remain mutable; a synchronous recorder that retains them owns the
    responsibility of keeping their lifetime and avoiding later mutation.
    Consequently this model is not frozen even though its diagnostic models are
    immutable.
    """

    frame_id: int
    frame_timestamp: datetime
    image: np.ndarray
    price_observation_image: np.ndarray | None
    chart_region: ChartRegion | None
    price_observation_region: ChartRegion | None
    source: str
    market_analysis: MarketAnalysis | None
    current_visual_price: CurrentVisualPriceExtraction | None
    visual_price_reference_result: VisualPriceReferenceResult | None
    candle_detection_trace: CandleDetectionTrace | None
    current_visual_price_detection_trace: (
        CurrentVisualPriceDetectionTrace | None
    )

    def __post_init__(self) -> None:
        if (
            not isinstance(self.frame_id, int)
            or isinstance(self.frame_id, bool)
            or self.frame_id <= 0
        ):
            raise ValueError("frame_id must be a positive integer.")
        if not isinstance(self.image, np.ndarray):
            raise TypeError("image must be a numpy.ndarray.")
        if (
            self.price_observation_image is not None
            and not isinstance(self.price_observation_image, np.ndarray)
        ):
            raise TypeError("price_observation_image must be a numpy.ndarray.")
        if not self.source.strip():
            raise ValueError("source cannot be empty.")
        self.frame_timestamp = _aware_utc(
            self.frame_timestamp,
            "frame_timestamp",
        )
        self._validate_market_analysis_evidence()

    @property
    def image_shape(self) -> tuple[int, ...]:
        """Return capture dimensions without storing a redundant copy."""

        return tuple(int(dimension) for dimension in self.image.shape)

    @property
    def price_observation_image_shape(self) -> tuple[int, ...] | None:
        """Return price-ROI dimensions when that capture exists."""

        if self.price_observation_image is None:
            return None
        return tuple(
            int(dimension) for dimension in self.price_observation_image.shape
        )

    def _validate_market_analysis_evidence(self) -> None:
        analysis = self.market_analysis
        if analysis is None:
            return
        identity_pairs = (
            (
                "current_visual_price",
                self.current_visual_price,
                analysis.current_visual_price,
            ),
            (
                "candle_detection_trace",
                self.candle_detection_trace,
                analysis.candle_detection_trace,
            ),
            (
                "current_visual_price_detection_trace",
                self.current_visual_price_detection_trace,
                analysis.current_visual_price_detection_trace,
            ),
        )
        for field_name, evidence_value, analysis_value in identity_pairs:
            if evidence_value is not analysis_value:
                raise ValueError(
                    f"{field_name} must come from the same MarketAnalysis."
                )


def _normalize_utc(instance: object, field_name: str) -> None:
    value = getattr(instance, field_name)
    object.__setattr__(instance, field_name, _aware_utc(value, field_name))


def _aware_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include timezone information.")
    return value.astimezone(UTC)
