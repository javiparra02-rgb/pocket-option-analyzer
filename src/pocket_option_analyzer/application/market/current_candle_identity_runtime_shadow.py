from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from threading import RLock

from pocket_option_analyzer.vision.models import (
    CandleOverlayEvidenceStatus,
    CandleOverlayEvidenceTrace,
    MarketAnalysis,
)

from .current_candle_identity import (
    CurrentCandleFrameContext,
    CurrentCandleIdentityResetReason,
    CurrentCandleIdentityResolution,
    CurrentCandleIdentityResult,
    CurrentCandleIdentitySource,
    CurrentCandleIdentityStatus,
    CurrentCandleIdentityTrace,
)
from .current_candle_identity_resolver import CurrentCandleIdentityResolver

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CurrentCandleIdentityFrameMetadata:
    """Capture-owned metadata propagated without recapture or reconstruction."""

    frame_id: int
    wall_timestamp: datetime
    monotonic_timestamp: float
    source_key: str
    session_key: str
    roi_width: int
    roi_height: int

    def __post_init__(self) -> None:
        if self.frame_id < 1:
            raise ValueError("frame_id debe ser positivo en runtime.")
        if not isinstance(self.wall_timestamp, datetime):
            raise TypeError("wall_timestamp debe ser datetime.")
        if (
            self.wall_timestamp.tzinfo is None
            or self.wall_timestamp.utcoffset() is None
        ):
            raise ValueError("wall_timestamp debe incluir zona horaria.")
        if not isfinite(self.monotonic_timestamp) or self.monotonic_timestamp < 0:
            raise ValueError("monotonic_timestamp debe ser finito y no negativo.")
        if not self.source_key or not self.session_key:
            raise ValueError("source_key y session_key no pueden estar vacíos.")
        if self.roi_width < 1 or self.roi_height < 1:
            raise ValueError("Las dimensiones del ROI deben ser positivas.")


class CurrentCandleIdentityFrameContextBuilder:
    """Build identity context from the exact same-pass MarketAnalysis trace."""

    def build(
        self,
        *,
        metadata: CurrentCandleIdentityFrameMetadata,
        market_analysis: MarketAnalysis,
    ) -> CurrentCandleFrameContext:
        """Reuse membership, final candles and overlay evidence by identity."""

        candle_trace = market_analysis.candle_detection_trace
        membership = (
            candle_trace.series_membership if candle_trace is not None else None
        )
        final_candles = candle_trace.final_candles if candle_trace is not None else ()
        overlay_evidence = (
            candle_trace.overlay_evidence if candle_trace is not None else None
        )
        expiry_line_x, expiry_line_conflict = self._expiry_vertical_line(
            overlay_evidence
        )
        return CurrentCandleFrameContext(
            frame_id=metadata.frame_id,
            wall_timestamp=metadata.wall_timestamp,
            monotonic_timestamp=metadata.monotonic_timestamp,
            roi_width=metadata.roi_width,
            roi_height=metadata.roi_height,
            source_key=metadata.source_key,
            session_key=metadata.session_key,
            membership=membership,
            final_candles=final_candles,
            overlay_evidence=overlay_evidence,
            expiry_vertical_line_x=expiry_line_x,
            expiry_vertical_line_conflict=expiry_line_conflict,
        )

    @staticmethod
    def _expiry_vertical_line(
        overlay_evidence: CandleOverlayEvidenceTrace | None,
    ) -> tuple[int | None, bool]:
        if overlay_evidence is None:
            return None, False
        overlays = tuple(
            evidence
            for evidence in overlay_evidence.evidence
            if evidence.status is CandleOverlayEvidenceStatus.EXPIRY_OVERLAY
        )
        if len(overlays) > 1:
            return None, True
        if not overlays:
            return None, False
        return overlays[0].vertical_line_x, False


class CurrentCandleIdentityRuntimeShadow:
    """Session-scoped in-memory façade over one stateful identity resolver."""

    def __init__(
        self,
        *,
        resolver: CurrentCandleIdentityResolver,
        context_builder: CurrentCandleIdentityFrameContextBuilder | None = None,
    ) -> None:
        self._resolver = resolver
        self._context_builder = (
            context_builder or CurrentCandleIdentityFrameContextBuilder()
        )
        self._lock = RLock()
        self._session_key: str | None = None
        self._resolver_started = False
        self._last_resolution: CurrentCandleIdentityResolution | None = None

    @property
    def resolver(self) -> CurrentCandleIdentityResolver:
        """Expose the session-owned resolver for diagnostics and DI tests."""

        return self._resolver

    @property
    def last_resolution(self) -> CurrentCandleIdentityResolution | None:
        """Return the last atomic shadow result/trace pair."""

        with self._lock:
            return self._last_resolution

    @property
    def session_key(self) -> str | None:
        """Return the active opaque runtime session key."""

        with self._lock:
            return self._session_key

    def start_session(self, *, session_key: str) -> None:
        """Start a logical runtime session before its first captured frame."""

        if not session_key:
            raise ValueError("session_key no puede estar vacío.")
        with self._lock:
            if self._resolver_started:
                self._resolver.stop_session()
            self._session_key = session_key
            self._resolver_started = False
            self._last_resolution = None

    def stop_session(self) -> None:
        """Clear resolver tracking even after normal or exceptional shutdown."""

        with self._lock:
            if self._resolver_started:
                self._resolver.stop_session()
            self._resolver_started = False
            self._session_key = None

    def resolve(
        self,
        *,
        metadata: CurrentCandleIdentityFrameMetadata,
        market_analysis: MarketAnalysis,
    ) -> CurrentCandleIdentityResolution:
        """Resolve identity from the same MarketAnalysis, shadow-only."""

        with self._lock:
            if self._session_key is None:
                raise RuntimeError("Current-candle identity session is not active.")
            if metadata.session_key != self._session_key:
                raise ValueError("Frame metadata belongs to another runtime session.")
            context = self._context_builder.build(
                metadata=metadata,
                market_analysis=market_analysis,
            )
            if not self._resolver_started:
                self._resolver.start_session(
                    source_key=metadata.source_key,
                    session_key=metadata.session_key,
                )
                self._resolver_started = True
            try:
                resolution = self._resolver.resolve_with_trace(
                    frame_context=context,
                )
            except OSError as error:
                resolution = self._operational_failure(context, error)
            self._last_resolution = resolution
            return resolution

    def _operational_failure(
        self,
        context: CurrentCandleFrameContext,
        error: OSError,
    ) -> CurrentCandleIdentityResolution:
        logger.exception("Current-candle identity shadow failed operationally.")
        self._resolver.reset(CurrentCandleIdentityResetReason.INTERNAL_ERROR)
        generation = self._resolver.continuity_generation
        diagnostic = f"runtime_shadow_operational_error:{type(error).__name__}"
        result = CurrentCandleIdentityResult(
            status=CurrentCandleIdentityStatus.UNAVAILABLE,
            candidate_id=None,
            source=CurrentCandleIdentitySource.NONE,
            terminal_region=None,
            estimated_pitch_px=context.estimated_pitch_px,
            continuity_generation=generation,
            evidence=None,
            diagnostics=(diagnostic,),
        )
        trace = CurrentCandleIdentityTrace(
            frame_id=context.frame_id,
            wall_timestamp=context.wall_timestamp,
            monotonic_timestamp=context.monotonic_timestamp,
            source_key=context.source_key,
            session_key=context.session_key,
            status=result.status,
            internal_state=self._resolver.lifecycle,
            continuity_generation=generation,
            legacy_latest_candidate_id=(
                context.membership.latest_candidate_id
                if context.membership is not None
                else None
            ),
            terminal_region=None,
            estimated_pitch_px=context.estimated_pitch_px,
            sequence_match=None,
            rollover_suspected=False,
            rollover_confirmed=False,
            chosen_candidate_id=None,
            missing_evidence=None,
            reset_reason=CurrentCandleIdentityResetReason.INTERNAL_ERROR,
            expiry_evidence_consistent=context.expiry_evidence_consistent,
            expiry_vertical_line_x=context.expiry_vertical_line_x,
            expiry_vertical_line_conflict=context.expiry_vertical_line_conflict,
            diagnostics=(diagnostic,),
        )
        return CurrentCandleIdentityResolution(result=result, trace=trace)
