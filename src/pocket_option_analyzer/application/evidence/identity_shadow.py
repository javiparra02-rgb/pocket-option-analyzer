from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from math import isfinite

import numpy as np

from pocket_option_analyzer.application.market.current_candle_identity import (
    CurrentCandleFrameContext,
    CurrentCandleIdentityResolution,
)
from pocket_option_analyzer.application.strategy.visual_price_reference_result import (
    VisualPriceReferenceResult,
)
from pocket_option_analyzer.vision.models import ChartRegion


class IdentityShadowPngMode(StrEnum):
    """Bounded PNG policy for optional identity evidence."""

    EVENT_ONLY = "event_only"
    ALL_FRAMES = "all_frames"


class IdentityShadowEventType(StrEnum):
    """Stable event vocabulary for continuous identity evidence."""

    LIFECYCLE_START = "lifecycle_start"
    LIFECYCLE_STOP = "lifecycle_stop"
    BOOTSTRAP_PENDING = "bootstrap_pending"
    BOOTSTRAP_CONFIRMED = "bootstrap_confirmed"
    ROLLOVER_SUSPECTED = "rollover_suspected"
    ROLLOVER_CONFIRMED = "rollover_confirmed"
    STATUS_CHANGED = "identity_status_changed"
    MISSING_FROM_VIEW = "missing_from_view"
    AMBIGUOUS = "ambiguous"
    RESET = "reset"
    RESOLVER_FAILURE = "resolver_failure"
    PERSISTENCE_FAILURE = "persistence_failure"
    CHECKPOINT = "checkpoint"


@dataclass(frozen=True, slots=True)
class IdentityShadowEvidenceConfig:
    """Opt-in persistence policy; defaults are diagnostic, not calibrated."""

    # Provisional diagnostic defaults pending P0.4b calibration.
    ring_buffer_size: int = 30
    pre_event_trace_count: int = 5
    png_mode: IdentityShadowPngMode = IdentityShadowPngMode.EVENT_ONLY
    checkpoint_interval_frames: int | None = None

    def __post_init__(self) -> None:
        if self.ring_buffer_size < 1:
            raise ValueError("ring_buffer_size must be positive.")
        if not 0 <= self.pre_event_trace_count <= self.ring_buffer_size:
            raise ValueError(
                "pre_event_trace_count must fit inside the ring buffer."
            )
        if not isinstance(self.png_mode, IdentityShadowPngMode):
            raise TypeError("png_mode must be an IdentityShadowPngMode.")
        if (
            self.checkpoint_interval_frames is not None
            and self.checkpoint_interval_frames < 1
        ):
            raise ValueError("checkpoint_interval_frames must be positive.")


@dataclass(slots=True)
class IdentityShadowFrameEvidence:
    """Borrowed same-pass input for diagnostic identity persistence.

    The image is intentionally not copied. Recorders must consume it
    synchronously and may not retain the mutable ndarray after the call.
    """

    frame_id: int
    frame_timestamp: datetime
    monotonic_timestamp: float
    source_key: str
    session_key: str
    roi_width: int
    roi_height: int
    image: np.ndarray
    chart_region: ChartRegion | None
    resolution: CurrentCandleIdentityResolution
    frame_context: CurrentCandleFrameContext
    visual_price_reference_result: VisualPriceReferenceResult | None

    def __post_init__(self) -> None:
        if self.frame_id < 1:
            raise ValueError("frame_id must be positive.")
        if not isinstance(self.image, np.ndarray):
            raise TypeError("image must be a numpy.ndarray.")
        if self.roi_width < 1 or self.roi_height < 1:
            raise ValueError("ROI dimensions must be positive.")
        if self.image.shape[:2] != (self.roi_height, self.roi_width):
            raise ValueError("ROI dimensions must match the analyzed image.")
        if not self.source_key or not self.session_key:
            raise ValueError("source_key and session_key cannot be empty.")
        if not isinstance(self.frame_timestamp, datetime):
            raise TypeError("frame_timestamp must be a datetime.")
        if (
            self.frame_timestamp.tzinfo is None
            or self.frame_timestamp.utcoffset() is None
        ):
            raise ValueError("frame_timestamp must include timezone information.")
        self.frame_timestamp = self.frame_timestamp.astimezone(UTC)
        if not isfinite(self.monotonic_timestamp) or self.monotonic_timestamp < 0:
            raise ValueError("monotonic_timestamp must be finite and non-negative.")
        self._validate_same_pass()

    def _validate_same_pass(self) -> None:
        trace = self.resolution.trace
        if trace.frame_id != self.frame_id:
            raise ValueError("Identity trace must belong to the same frame_id.")
        if trace.wall_timestamp.astimezone(UTC) != self.frame_timestamp:
            raise ValueError("Identity trace must use the same wall timestamp.")
        if trace.monotonic_timestamp != self.monotonic_timestamp:
            raise ValueError("Identity trace must use the same monotonic timestamp.")
        if trace.source_key != self.source_key:
            raise ValueError("Identity trace must use the same source_key.")
        if trace.session_key != self.session_key:
            raise ValueError("Identity trace must use the same session_key.")
        context = self.frame_context
        if context.frame_id != self.frame_id:
            raise ValueError("Identity context must belong to the same frame_id.")
        if context.wall_timestamp.astimezone(UTC) != self.frame_timestamp:
            raise ValueError("Identity context must use the same wall timestamp.")
        if context.monotonic_timestamp != self.monotonic_timestamp:
            raise ValueError("Identity context must use the same monotonic timestamp.")
        if context.source_key != self.source_key:
            raise ValueError("Identity context must use the same source_key.")
        if context.session_key != self.session_key:
            raise ValueError("Identity context must use the same session_key.")
        if (context.roi_width, context.roi_height) != (
            self.roi_width,
            self.roi_height,
        ):
            raise ValueError("Identity context must use the same ROI dimensions.")
        membership = context.membership
        latest_candidate_id = (
            membership.latest_candidate_id if membership is not None else None
        )
        if latest_candidate_id != trace.legacy_latest_candidate_id:
            raise ValueError(
                "Identity trace and same-pass membership disagree on legacy latest."
            )
