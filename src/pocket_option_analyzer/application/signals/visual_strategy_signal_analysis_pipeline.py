from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

import numpy as np

from pocket_option_analyzer.application.market import (
    CandleIntervalIndicatorCacheStatus,
    CurrentCandleIdentityFrameMetadata,
    CurrentCandleIdentityResolution,
    CurrentCandleIdentityResult,
    CurrentCandleIdentityRuntimeShadow,
    CurrentCandleIdentityTrace,
    VisualEntryContextAnalyzer,
    VisualIndicatorSnapshotBuilder,
    VisualIndicatorSnapshotContext,
)
from pocket_option_analyzer.application.signals.strategy_signal_generator import (
    StrategySignalGenerator,
)
from pocket_option_analyzer.application.strategy import (
    CurrentVisualPriceComparisonContext,
    DirectionConditionAudit,
    StrategyCondition,
    StrategyConditionAudit,
    StrategyObservation,
    VisualPriceReference,
    VisualPriceReferenceResult,
    VisualPriceReferenceStatus,
)
from pocket_option_analyzer.domain.indicators import IndicatorSnapshot
from pocket_option_analyzer.domain.signals import MarketSignal, SignalDirection
from pocket_option_analyzer.domain.strategy import StrategyProfile
from pocket_option_analyzer.vision.models import (
    CandleAnchorExclusionReason,
    CandleType,
    ChartRegion,
    ClassifiedCandle,
    CurrentVisualPriceExtraction,
    MarketAnalysis,
)
from pocket_option_analyzer.vision.services import MarketAnalysisPipeline


@dataclass(frozen=True, slots=True)
class _ObservationData:
    audit: StrategyConditionAudit
    market_analysis: MarketAnalysis
    indicators: IndicatorSnapshot
    context: VisualIndicatorSnapshotContext | None
    timing: CandleIntervalIndicatorCacheStatus
    direction: SignalDirection
    visual_price_comparison_context: CurrentVisualPriceComparisonContext


@dataclass(frozen=True, slots=True)
class _VisualPriceReferenceAnalysis:
    result: VisualPriceReferenceResult
    latest: ClassifiedCandle | None
    anchors: tuple[ClassifiedCandle, ...] | None


class VisualStrategySignalAnalysisPipeline:
    """
    Pipeline de señales basado completamente en análisis visual.

    Flujo:
    - imagen capturada
    - análisis visual de mercado
    - serie visual de velas
    - indicadores derivados visualmente
    - evaluación de estrategia
    - señal CALL / PUT / NONE

    No ejecuta operaciones.
    No interactúa con Pocket Option.
    Solo analiza información visual.
    """

    def __init__(
        self,
        market_analysis_pipeline: MarketAnalysisPipeline,
        indicator_snapshot_builder: VisualIndicatorSnapshotBuilder,
        signal_generator: StrategySignalGenerator,
        profile: StrategyProfile,
        entry_context_analyzer: VisualEntryContextAnalyzer | None = None,
        current_candle_identity_shadow: (
            CurrentCandleIdentityRuntimeShadow | None
        ) = None,
    ) -> None:
        self._market_analysis_pipeline = market_analysis_pipeline
        self._indicator_snapshot_builder = indicator_snapshot_builder
        self._signal_generator = signal_generator
        self._profile = profile
        self._entry_context_analyzer = (
            entry_context_analyzer
            if entry_context_analyzer is not None
            else VisualEntryContextAnalyzer()
        )
        self._current_candle_identity_shadow = current_candle_identity_shadow
        self._last_observation_data: _ObservationData | None = None
        self._last_price_reference: VisualPriceReference | None = None
        self._last_price_reference_result: VisualPriceReferenceResult | None = None
        self._last_current_visual_price: CurrentVisualPriceExtraction | None = None
        self._last_visual_price_comparison_context: (
            CurrentVisualPriceComparisonContext | None
        ) = None
        self._last_market_analysis: MarketAnalysis | None = None
        self._last_current_candle_identity_resolution: (
            CurrentCandleIdentityResolution | None
        ) = None

    @property
    def last_price_reference(self) -> VisualPriceReference | None:
        return self._last_price_reference

    @property
    def last_price_reference_result(
        self,
    ) -> VisualPriceReferenceResult | None:
        """
        Devuelve el diagnóstico de la última referencia visual calculada.
        """

        return self._last_price_reference_result

    @property
    def last_current_visual_price(
        self,
    ) -> CurrentVisualPriceExtraction | None:
        """Return the visual-price extraction from the last analyzed frame."""

        return self._last_current_visual_price

    @property
    def last_visual_price_comparison_context(
        self,
    ) -> CurrentVisualPriceComparisonContext | None:
        """Return the comparison evidence from the last analyzed frame."""

        return self._last_visual_price_comparison_context

    @property
    def last_market_analysis(self) -> MarketAnalysis | None:
        """Devuelve el análisis del último frame, incluida su traza inmutable."""

        return self._last_market_analysis

    @property
    def last_current_candle_identity_resolution(
        self,
    ) -> CurrentCandleIdentityResolution | None:
        """Return the last atomic shadow result and diagnostic trace."""

        return self._last_current_candle_identity_resolution

    @property
    def last_current_candle_identity_result(
        self,
    ) -> CurrentCandleIdentityResult | None:
        """Return the last shadow result without affecting legacy analysis."""

        resolution = self._last_current_candle_identity_resolution
        return resolution.result if resolution is not None else None

    @property
    def last_current_candle_identity(
        self,
    ) -> CurrentCandleIdentityResult | None:
        """Return the public in-memory shadow conclusion for the last frame."""

        return self.last_current_candle_identity_result

    @property
    def last_current_candle_identity_trace(
        self,
    ) -> CurrentCandleIdentityTrace | None:
        """Return the trace paired atomically with the last shadow result."""

        resolution = self._last_current_candle_identity_resolution
        return resolution.trace if resolution is not None else None

    @property
    def current_candle_identity_shadow(
        self,
    ) -> CurrentCandleIdentityRuntimeShadow | None:
        """Expose the injected session-owned shadow for diagnostics."""

        return self._current_candle_identity_shadow

    def start_session(self, *, session_key: str) -> None:
        """Start the optional identity shadow for a runtime session."""

        if self._current_candle_identity_shadow is not None:
            self._current_candle_identity_shadow.start_session(
                session_key=session_key,
            )
        self._last_current_candle_identity_resolution = None

    def stop_session(self) -> None:
        """Stop tracking while retaining the last immutable diagnostic result."""

        if self._current_candle_identity_shadow is not None:
            self._current_candle_identity_shadow.stop_session()

    def build_last_observation(
        self,
        observed_at: datetime,
    ) -> StrategyObservation | None:
        """Build the structured observation produced by the last analysis."""

        data = self._last_observation_data
        if data is None or data.timing.cached_key is None:
            return None
        return StrategyObservation(
            observed_at=observed_at,
            candle_interval_started_at=data.timing.cached_key.started_at,
            audit=data.audit,
            trend=data.market_analysis.trend,
            indicators=data.indicators,
            resolve_at=StrategyObservation.resolve_time(observed_at),
            direction=(
                data.direction
                if data.direction in (SignalDirection.CALL, SignalDirection.PUT)
                else None
            ),
            entry_reference=(
                data.visual_price_comparison_context.reference_result.reference
            ),
            entry_reference_result=(
                data.visual_price_comparison_context.reference_result
            ),
            current_visual_price=(
                data.visual_price_comparison_context.current_visual_price
            ),
            visual_context=data.context,
            detection_diagnostics=data.market_analysis.detection_diagnostics,
            visual_price_comparison_context=(data.visual_price_comparison_context),
        )

    def analyze(
        self,
        image: np.ndarray,
        price_observation_image: np.ndarray | None = None,
        chart_region: ChartRegion | None = None,
        price_observation_region: ChartRegion | None = None,
        frame_id: int | None = None,
        frame_timestamp: datetime | None = None,
        monotonic_timestamp: float | None = None,
        source_key: str | None = None,
        session_key: str | None = None,
    ) -> MarketSignal:
        """
        Analiza una imagen y devuelve una señal de mercado.

        El diagnóstico visual se entrega siempre, incluso cuando faltan
        velas para calcular indicadores.
        """

        self._last_observation_data = None
        self._last_price_reference = None
        self._last_price_reference_result = None
        self._last_current_visual_price = None
        self._last_visual_price_comparison_context = None
        self._last_market_analysis = None
        self._last_current_candle_identity_resolution = None

        market_analysis = self._market_analysis_pipeline.analyze(
            image=image,
            price_observation_image=price_observation_image,
            chart_region=chart_region,
            price_observation_region=price_observation_region,
        )
        self._last_current_visual_price = market_analysis.current_visual_price

        identity_metadata = self._identity_metadata(
            image=image,
            frame_id=frame_id,
            frame_timestamp=frame_timestamp,
            monotonic_timestamp=monotonic_timestamp,
            source_key=source_key,
            session_key=session_key,
        )
        if (
            self._current_candle_identity_shadow is not None
            and identity_metadata is not None
        ):
            self._last_current_candle_identity_resolution = (
                self._current_candle_identity_shadow.resolve(
                    metadata=identity_metadata,
                    market_analysis=market_analysis,
                )
            )

        reference_analysis = self._price_reference_analysis(
            market_analysis=market_analysis,
        )
        reference_result = reference_analysis.result
        market_analysis = self._with_reference_roles(
            market_analysis=market_analysis,
            reference_analysis=reference_analysis,
        )
        self._last_market_analysis = market_analysis

        self._last_price_reference_result = reference_result
        self._last_price_reference = reference_result.reference
        visual_price_comparison_context = CurrentVisualPriceComparisonContext(
            current_visual_price=market_analysis.current_visual_price,
            chart_region=market_analysis.chart_region,
            price_observation_region=market_analysis.price_observation_region,
            reference_result=reference_result,
        )
        self._last_visual_price_comparison_context = visual_price_comparison_context

        indicators = self._indicator_snapshot_builder.build(
            series=market_analysis.series,
            profile=self._profile,
        )

        if indicators is None:
            not_enough_reason = self._not_enough_candles_reason(
                detected_candles=len(
                    market_analysis.series,
                ),
            )

            visual_diagnostics_line = self._visual_diagnostics_line(
                market_analysis=market_analysis,
                signal_state_label="SIN_INDICADORES",
            )

            return MarketSignal.neutral(
                reason=(
                    f"{visual_diagnostics_line}\n"
                    f"{self._missing_indicator_diagnostics_line()}\n"
                    f"{not_enough_reason}"
                ),
            )

        snapshot_timing_status = self._resolve_snapshot_timing_status()

        if (
            snapshot_timing_status is not None
            and not snapshot_timing_status.allows_actionable_signals
        ):
            visual_diagnostics_line = self._visual_diagnostics_line(
                market_analysis=market_analysis,
                signal_state_label=("ESPERANDO_SNAPSHOT_NUEVO"),
            )

            indicator_diagnostics_line = self._indicator_diagnostics_line(
                indicators=indicators,
                snapshot_context=(self._indicator_snapshot_builder.snapshot_context),
                snapshot_timing_status=(snapshot_timing_status),
            )

            return MarketSignal.neutral(
                reason=(
                    f"{visual_diagnostics_line}\n"
                    f"{indicator_diagnostics_line}\n"
                    f"{
                        self._snapshot_timing_line(
                            status=snapshot_timing_status,
                        )
                    }"
                ),
            )

        signal = self._signal_generator.generate(
            analysis=market_analysis,
            indicators=indicators,
        )

        audit = getattr(self._signal_generator, "last_condition_audit", None)
        if (
            isinstance(audit, StrategyConditionAudit)
            and snapshot_timing_status is not None
            and snapshot_timing_status.is_current
        ):
            self._last_observation_data = _ObservationData(
                audit=audit,
                market_analysis=market_analysis,
                indicators=indicators,
                context=self._indicator_snapshot_builder.snapshot_context,
                timing=snapshot_timing_status,
                direction=signal.direction,
                visual_price_comparison_context=(visual_price_comparison_context),
            )

        visual_diagnostics_line = self._visual_diagnostics_line(
            market_analysis=market_analysis,
            signal_state_label=self._signal_state_label(
                signal=signal,
            ),
        )

        return MarketSignal(
            direction=signal.direction,
            strength=signal.strength,
            reason=(
                f"{visual_diagnostics_line}\n"
                f"{
                    self._indicator_diagnostics_line(
                        indicators=indicators,
                        snapshot_context=(
                            self._indicator_snapshot_builder.snapshot_context
                        ),
                        snapshot_timing_status=(snapshot_timing_status),
                    )
                }\n"
                f"{signal.reason}"
                f"{self._strategy_diagnostics_suffix()}"
            ),
        )

    @staticmethod
    def _identity_metadata(
        *,
        image: np.ndarray,
        frame_id: int | None,
        frame_timestamp: datetime | None,
        monotonic_timestamp: float | None,
        source_key: str | None,
        session_key: str | None,
    ) -> CurrentCandleIdentityFrameMetadata | None:
        if session_key is None:
            return None
        values = (
            frame_id,
            frame_timestamp,
            monotonic_timestamp,
            source_key,
        )
        if any(value is None for value in values):
            raise ValueError(
                "Current-candle identity runtime metadata must be complete."
            )
        assert frame_id is not None
        assert frame_timestamp is not None
        assert monotonic_timestamp is not None
        assert source_key is not None
        assert session_key is not None
        return CurrentCandleIdentityFrameMetadata(
            frame_id=frame_id,
            wall_timestamp=frame_timestamp,
            monotonic_timestamp=monotonic_timestamp,
            source_key=source_key,
            session_key=session_key,
            roi_width=int(image.shape[1]),
            roi_height=int(image.shape[0]),
        )

    @staticmethod
    def _price_reference_result(
        market_analysis: MarketAnalysis,
    ) -> VisualPriceReferenceResult:
        """
        Calcula la referencia visual del precio y conserva el motivo
        exacto cuando no puede producir una referencia fiable.

        Este método no relaja ninguna condición de comparabilidad.
        La referencia conserva la coordenada afín completa, incluidos
        breakouts fuera del rango cerrado de las anclas.
        """

        return VisualStrategySignalAnalysisPipeline._price_reference_analysis(
            market_analysis=market_analysis,
        ).result

    @staticmethod
    def _price_reference_analysis(
        market_analysis: MarketAnalysis,
    ) -> _VisualPriceReferenceAnalysis:
        """Construye la referencia y conserva las selecciones ya realizadas."""

        latest = market_analysis.series.latest

        if latest is None:
            return _VisualPriceReferenceAnalysis(
                result=VisualPriceReferenceResult(
                    reference=None,
                    status=VisualPriceReferenceStatus.LATEST_CANDLE_MISSING,
                ),
                latest=None,
                anchors=None,
            )

        latest_candidate = latest.candidate
        latest_geometry = latest_candidate.geometry

        if latest_geometry is None:
            return _VisualPriceReferenceAnalysis(
                result=VisualPriceReferenceResult(
                    reference=None,
                    status=VisualPriceReferenceStatus.LATEST_GEOMETRY_MISSING,
                    latest_candle_type=latest.candle_type.value,
                    latest_candidate_x=latest_candidate.x,
                    latest_candidate_y=latest_candidate.y,
                ),
                latest=latest,
                anchors=None,
            )

        anchor_candles = tuple(
            candle
            for candle in market_analysis.series.without_latest().candles
            if (
                candle.candle_type is not CandleType.UNKNOWN
                and candle.candidate.geometry is not None
            )
        )

        if len(anchor_candles) < 2:
            return _VisualPriceReferenceAnalysis(
                result=VisualPriceReferenceResult(
                    reference=None,
                    status=VisualPriceReferenceStatus.INSUFFICIENT_ANCHORS,
                    anchor_count=len(anchor_candles),
                    latest_candle_type=latest.candle_type.value,
                    latest_candidate_x=latest_candidate.x,
                    latest_candidate_y=latest_candidate.y,
                ),
                latest=latest,
                anchors=anchor_candles,
            )

        chart_top_roi_y = min(
            candle.candidate.geometry.high_y  # type: ignore[union-attr]
            for candle in anchor_candles
        )

        chart_bottom_roi_y = max(
            candle.candidate.geometry.low_y  # type: ignore[union-attr]
            for candle in anchor_candles
        )

        chart_range_roi_px = chart_bottom_roi_y - chart_top_roi_y

        if chart_range_roi_px <= 0:
            return _VisualPriceReferenceAnalysis(
                result=VisualPriceReferenceResult(
                    reference=None,
                    status=VisualPriceReferenceStatus.ZERO_ANCHOR_RANGE,
                    anchor_count=len(anchor_candles),
                    latest_candle_type=latest.candle_type.value,
                    latest_candidate_x=latest_candidate.x,
                    latest_candidate_y=latest_candidate.y,
                    anchor_top_roi_y=chart_top_roi_y,
                    anchor_bottom_roi_y=chart_bottom_roi_y,
                ),
                latest=latest,
                anchors=anchor_candles,
            )

        if latest.candle_type is CandleType.BULLISH:
            close_roi_y = latest_geometry.body_top_y

        elif latest.candle_type is CandleType.BEARISH:
            close_roi_y = latest_geometry.body_bottom_y

        else:
            return _VisualPriceReferenceAnalysis(
                result=VisualPriceReferenceResult(
                    reference=None,
                    status=VisualPriceReferenceStatus.LATEST_CANDLE_NOT_DIRECTIONAL,
                    anchor_count=len(anchor_candles),
                    latest_candle_type=latest.candle_type.value,
                    latest_candidate_x=latest_candidate.x,
                    latest_candidate_y=latest_candidate.y,
                    anchor_top_roi_y=chart_top_roi_y,
                    anchor_bottom_roi_y=chart_bottom_roi_y,
                ),
                latest=latest,
                anchors=anchor_candles,
            )

        raw_normalized_close = (chart_bottom_roi_y - close_roi_y) / chart_range_roi_px

        observability = latest_candidate.observability
        if (
            observability is None
            or observability.fully_observable_close_for(latest.candle_type) is not True
        ):
            return _VisualPriceReferenceAnalysis(
                result=VisualPriceReferenceResult(
                    reference=None,
                    status=(
                        VisualPriceReferenceStatus.CURRENT_CLOSE_NOT_OBSERVABLE
                    ),
                    anchor_count=len(anchor_candles),
                    latest_candle_type=latest.candle_type.value,
                    latest_candidate_x=latest_candidate.x,
                    latest_candidate_y=latest_candidate.y,
                    close_roi_y=close_roi_y,
                    anchor_top_roi_y=chart_top_roi_y,
                    anchor_bottom_roi_y=chart_bottom_roi_y,
                    raw_normalized_close=raw_normalized_close,
                ),
                latest=latest,
                anchors=anchor_candles,
            )

        def normalize(
            roi_y: int,
        ) -> float:
            return (chart_bottom_roi_y - roi_y) / chart_range_roi_px

        anchor_shape = tuple(
            (
                candle.candle_type.value,
                normalize(
                    candle.candidate.geometry.high_y,  # type: ignore[union-attr]
                ),
                normalize(
                    candle.candidate.geometry.body_top_y,  # type: ignore[union-attr]
                ),
                normalize(
                    candle.candidate.geometry.body_bottom_y,  # type: ignore[union-attr]
                ),
                normalize(
                    candle.candidate.geometry.low_y,  # type: ignore[union-attr]
                ),
            )
            for candle in anchor_candles
        )

        reference = VisualPriceReference(
            value=raw_normalized_close,
            anchor_shape=anchor_shape,
        )

        return _VisualPriceReferenceAnalysis(
            result=VisualPriceReferenceResult(
                reference=reference,
                status=VisualPriceReferenceStatus.OK,
                anchor_count=len(anchor_candles),
                latest_candle_type=latest.candle_type.value,
                latest_candidate_x=latest_candidate.x,
                latest_candidate_y=latest_candidate.y,
                close_roi_y=close_roi_y,
                anchor_top_roi_y=chart_top_roi_y,
                anchor_bottom_roi_y=chart_bottom_roi_y,
                raw_normalized_close=raw_normalized_close,
            ),
            latest=latest,
            anchors=anchor_candles,
        )

    @staticmethod
    def _with_reference_roles(
        *,
        market_analysis: MarketAnalysis,
        reference_analysis: _VisualPriceReferenceAnalysis,
    ) -> MarketAnalysis:
        trace = market_analysis.candle_detection_trace
        if trace is None or not trace.final_candles:
            return market_analysis

        anchors = reference_analysis.anchors
        anchor_indices = (
            {id(candle): index for index, candle in enumerate(anchors)}
            if anchors is not None
            else {}
        )
        if trace.series_membership is not None:
            member_ids = trace.series_membership.member_candidate_ids
            if len(member_ids) != len(market_analysis.series.candles):
                raise ValueError(
                    "La serie productiva debe coincidir con los IDs miembros."
                )
            candles_by_candidate_id = dict(
                zip(
                    member_ids,
                    market_analysis.series.candles,
                    strict=True,
                )
            )
            candle_trace_pairs = tuple(
                (
                    candles_by_candidate_id.get(final_trace.candidate_id),
                    final_trace,
                )
                for final_trace in trace.final_candles
            )
        else:
            candle_trace_pairs = tuple(
                zip(
                    market_analysis.series.candles,
                    trace.final_candles,
                    strict=True,
                )
            )
        updated_candles = []
        for candle, final_trace in candle_trace_pairs:
            if candle is None:
                updated_candles.append(
                    replace(
                        final_trace,
                        is_latest=False,
                        is_anchor=False,
                        anchor_index=None,
                        anchor_exclusion_reason=(
                            CandleAnchorExclusionReason.NOT_EVALUATED
                        ),
                    )
                )
                continue
            is_latest = candle is reference_analysis.latest
            anchor_index = anchor_indices.get(id(candle))
            is_anchor = anchor_index is not None
            if is_anchor:
                exclusion_reason = None
            elif is_latest:
                exclusion_reason = CandleAnchorExclusionReason.LATEST
            elif anchors is None:
                exclusion_reason = CandleAnchorExclusionReason.NOT_EVALUATED
            elif candle.candidate.geometry is None:
                exclusion_reason = CandleAnchorExclusionReason.MISSING_GEOMETRY
            else:
                exclusion_reason = CandleAnchorExclusionReason.UNKNOWN_CANDLE_TYPE
            updated_candles.append(
                replace(
                    final_trace,
                    is_latest=is_latest,
                    is_anchor=is_anchor,
                    anchor_index=anchor_index,
                    anchor_exclusion_reason=exclusion_reason,
                )
            )
        return replace(
            market_analysis,
            candle_detection_trace=replace(
                trace,
                final_candles=tuple(updated_candles),
            ),
        )

    def _strategy_diagnostics_suffix(self) -> str:
        """Format the exact audit used by the generator, if it exposes one."""

        audit = getattr(self._signal_generator, "last_condition_audit", None)

        if not isinstance(audit, StrategyConditionAudit):
            return ""

        return f"\n{self._strategy_diagnostics_block(audit)}"

    def _strategy_diagnostics_block(
        self,
        audit: StrategyConditionAudit,
    ) -> str:
        return (
            "[strategy_diagnostics] Diagnóstico de estrategia STRICT:\n"
            f"{self._direction_audit_lines(audit.call)}\n"
            f"{self._direction_audit_lines(audit.put)}"
        )

    def _direction_audit_lines(
        self,
        audit: DirectionConditionAudit,
    ) -> str:
        condition_labels = {
            StrategyCondition.TREND: "Tendencia",
            StrategyCondition.EMA_ALIGNMENT: "Alineación EMA",
            StrategyCondition.EMA_SEPARATION: "Separación EMA",
            StrategyCondition.RSI_RANGE: "Rango RSI",
            StrategyCondition.STOCHASTIC_CROSS: "Cruce Stochastic",
            StrategyCondition.STOCHASTIC_TRIGGER_ZONE: "Zona prevK",
            StrategyCondition.RECENT_CANDLE_CONFIRMATION: "Vela reciente",
        }
        lines = [
            f"  {audit.direction.name}: {audit.passed_count}/{audit.total_count}",
        ]

        for result in audit.conditions:
            state = "✅" if result.passed else "❌"
            blocker = " — BLOQUEA" if not result.passed else ""
            lines.append(f"    {state} {condition_labels[result.condition]}{blocker}")

        return "\n".join(lines)

    def _not_enough_candles_reason(
        self,
        detected_candles: int,
    ) -> str:
        return (
            "Not enough visual candles to calculate indicators. "
            f"Detected candles: {detected_candles}. "
            f"Minimum visible required: {self._minimum_required_visible_candles()}. "
            f"Minimum closed required: {self._minimum_required_closed_candles()}."
        )

    def _minimum_required_visible_candles(
        self,
    ) -> int:
        """
        Cantidad mínima de velas visibles necesarias.

        La última vela visible suele estar en formación, por lo que se exige
        una vela adicional para asegurar suficientes velas cerradas.
        """

        return self._minimum_required_closed_candles() + 1

    def _minimum_required_closed_candles(
        self,
    ) -> int:
        ema_required = self._profile.ema_slow_period

        rsi_required = self._profile.rsi_period + 1

        stochastic_required = (
            self._profile.stoch_k_period
            + self._profile.stoch_smooth_period
            + self._profile.stoch_d_period
            - 1
        )

        return max(
            ema_required,
            rsi_required,
            stochastic_required,
        )

    def _visual_diagnostics_line(
        self,
        market_analysis,
        signal_state_label: str,
    ) -> str:

        candles = tuple(
            market_analysis.series.candles,
        )

        latest_candles = candles[-3:]

        closed_candles = tuple(
            market_analysis.series.without_latest().candles,
        )

        recent_closed_candles = closed_candles[-3:]

        recent_directional_closed_candles = self._recent_directional_candles(
            candles=closed_candles,
            limit=3,
        )

        latest_text = self._candle_types_text(
            latest_candles,
        )
        recent_closed_text = self._candle_types_text(
            recent_closed_candles,
        )
        directional_closed_text = self._candle_types_text(
            recent_directional_closed_candles,
        )

        detection_diagnostics_block = self._detection_diagnostics_block(
            diagnostics=market_analysis.detection_diagnostics,
        )

        entry_context = self._entry_context_analyzer.analyze_directional(
            trend=market_analysis.trend,
            candles=recent_directional_closed_candles,
        )

        return (
            "[visual_diagnostics] "
            "Diagnóstico visual:\n"
            f"  Tendencia: {market_analysis.trend.name}\n"
            f"  Velas detectadas: {len(market_analysis.series)}\n"
            f"  Últimas: {latest_text}\n"
            f"  Cerradas: {recent_closed_text}\n"
            f"  Direccionales: {directional_closed_text}\n"
            f"{detection_diagnostics_block}"
            f"  Contexto: {entry_context.context_label}\n"
            f"  Vigilancia: {self._watch_label(entry_context.entry_state_label)}\n"
            f"  Estado: {signal_state_label}"
        )

    def _detection_diagnostics_block(
        self,
        diagnostics,
    ) -> str:
        """
        Formatea las etapas internas de CandleFilter para la GUI.

        Cuando el análisis proviene de un fake o integración que no
        proporciona diagnóstico, no añade ninguna línea.
        """

        if diagnostics is None:
            return ""

        dominant_width_label = (
            f"{diagnostics.dominant_width:.2f} px"
            if diagnostics.dominant_width is not None
            else "no disponible"
        )

        return (
            "  Detección: "
            f"segmentados={diagnostics.input_count} | "
            f"dimensiones={diagnostics.dimension_valid_count} | "
            f"ancho={diagnostics.width_valid_count} | "
            f"fusionados={diagnostics.merged_count} | "
            f"devueltos={diagnostics.returned_count}\n"
            "  Reducción detección: "
            f"dimensiones={diagnostics.rejected_by_dimensions} | "
            f"ancho={diagnostics.rejected_by_width} | "
            "fragmentos fusionados="
            f"{diagnostics.merged_fragments} | "
            f"límite={diagnostics.truncated_count}\n"
            f"  Ancho dominante: {dominant_width_label}\n"
        )

    def _recent_directional_candles(
        self,
        candles,
        limit: int,
    ):

        directional_candles = [
            candle
            for candle in candles
            if candle.candle_type.name
            in {
                "BULLISH",
                "BEARISH",
            }
        ]

        return tuple(directional_candles[-limit:])

    def _candle_types_text(
        self,
        candles,
    ) -> str:

        labels = [candle.candle_type.name for candle in candles]

        return (
            ", ".join(
                labels,
            )
            if labels
            else "NONE"
        )

    def _watch_label(
        self,
        entry_state_label: str,
    ) -> str:

        if entry_state_label == "BUSCAR_PUT":
            return "VIGILAR_PUT"

        if entry_state_label == "BUSCAR_CALL":
            return "VIGILAR_CALL"

        return "ESPERAR"

    def _signal_state_label(
        self,
        signal: MarketSignal,
    ) -> str:

        if signal.is_actionable:
            return "SEÑAL_CONFIRMADA"

        return "ESPERANDO_CONFIRMACION"

    def _missing_indicator_diagnostics_line(
        self,
    ) -> str:
        return (
            "[indicator_diagnostics] "
            "Diagnóstico de indicadores:\n"
            "  EMA: no disponible\n"
            "  RSI: no disponible\n"
            "  Stochastic: no disponible\n"
            "  Estado: velas insuficientes"
        )

    def _indicator_diagnostics_line(
        self,
        indicators,
        snapshot_context: (VisualIndicatorSnapshotContext | None),
        snapshot_timing_status: (CandleIntervalIndicatorCacheStatus | None) = None,
    ) -> str:

        indicator_state = (
            "esperando snapshot nuevo"
            if (
                snapshot_timing_status is not None
                and not snapshot_timing_status.is_current
            )
            else "esperando confirmación de estrategia"
        )

        return (
            "[indicator_diagnostics] "
            "Diagnóstico de indicadores:\n"
            f"  {self._ema_label(indicators)}\n"
            f"  {self._rsi_label(indicators)}\n"
            f"  {self._stochastic_label(indicators)}\n"
            f"{
                self._stochastic_audit_lines(
                    indicators=indicators,
                    snapshot_context=snapshot_context,
                )
            }\n"
            f"  Estado: {indicator_state}"
        )

    def _resolve_snapshot_timing_status(
        self,
    ) -> CandleIntervalIndicatorCacheStatus | None:
        """
        Obtiene el estado temporal sin romper fakes o adaptadores antiguos.
        """

        return getattr(
            self._indicator_snapshot_builder,
            "snapshot_timing_status",
            None,
        )

    def _snapshot_timing_line(
        self,
        status: CandleIntervalIndicatorCacheStatus,
    ) -> str:
        """
        Informa por qué una CALL o PUT está temporalmente bloqueada.
        """

        requested_label = status.requested_key.started_at.strftime(
            "%H:%M:%S",
        )

        cached_label = (
            status.cached_key.started_at.strftime(
                "%H:%M:%S",
            )
            if status.cached_key is not None
            else "NO_DISPONIBLE"
        )

        return (
            "[snapshot_timing] Snapshot temporal:\n"
            "  intervalo solicitado="
            f"{requested_label}\n"
            "  intervalo almacenado="
            f"{cached_label}\n"
            f"  estado={status.state_label}\n"
            "  Entrada: ESPERAR — el snapshot de indicadores "
            "todavía no pertenece a la vela actual."
        )

    def _ema_label(
        self,
        indicators,
    ) -> str:

        if indicators.ema.is_bullish_alignment:
            alignment = "alcista"
        elif indicators.ema.is_bearish_alignment:
            alignment = "bajista"
        else:
            alignment = "neutral"

        separation_state = (
            "suficiente"
            if (
                indicators.ema.separation_candles
                >= self._profile.ema_min_separation_candles
            )
            else "insuficiente"
        )

        return (
            "EMA: "
            f"{alignment} | "
            f"rápida={indicators.ema.fast_value:.2f} | "
            f"lenta={indicators.ema.slow_value:.2f} | "
            "separación="
            f"{indicators.ema.separation_candles}/"
            f"{self._profile.ema_min_separation_candles} "
            f"{separation_state}"
        )

    def _rsi_label(
        self,
        indicators,
    ) -> str:

        call_state = (
            "CALL en rango"
            if indicators.rsi.is_between(
                self._profile.rsi_call_min,
                self._profile.rsi_call_max,
            )
            else "CALL fuera de rango"
        )

        put_state = (
            "PUT en rango"
            if indicators.rsi.is_between(
                self._profile.rsi_put_min,
                self._profile.rsi_put_max,
            )
            else "PUT fuera de rango"
        )

        return f"RSI: {indicators.rsi.value:.2f} | {call_state} | {put_state}"

    def _stochastic_label(
        self,
        indicators,
    ) -> str:

        if indicators.stochastic.crossed_up:
            cross = "cruce alcista"
        elif indicators.stochastic.crossed_down:
            cross = "cruce bajista"
        else:
            cross = "sin cruce"

        return (
            "Stochastic: "
            f"{cross} | "
            f"K={indicators.stochastic.k_value:.2f} | "
            f"D={indicators.stochastic.d_value:.2f} | "
            f"prevK={indicators.stochastic.k_previous:.2f} | "
            f"prevD={indicators.stochastic.d_previous:.2f}"
        )

    def _stochastic_audit_lines(
        self,
        indicators,
        snapshot_context: (VisualIndicatorSnapshotContext | None),
    ) -> str:
        """
        Formatea el Stochastic y el contexto exacto del snapshot.

        No mezcla los conteos almacenados con la captura visual actual.
        """

        diagnostics = indicators.stochastic.diagnostics

        if diagnostics is None:
            return "  Auditoría Stoch: no disponible"

        snapshot_source_line = self._stochastic_snapshot_source_line(
            diagnostics=diagnostics,
            snapshot_context=snapshot_context,
        )

        return (
            f"{snapshot_source_line}\n"
            "  Auditoría Stoch OHLC: "
            f"máximo={diagnostics.highest_high:.2f} | "
            f"mínimo={diagnostics.lowest_low:.2f} | "
            f"cierre={diagnostics.latest_close:.2f} | "
            f"rango={diagnostics.price_range:.2f}\n"
            "  Auditoría Stoch cálculo: "
            f"K bruto={diagnostics.latest_raw_k:.2f} | "
            "K suavizado="
            f"{diagnostics.latest_smoothed_k:.2f} | "
            f"D={diagnostics.latest_d:.2f}"
        )

    def _stochastic_snapshot_source_line(
        self,
        diagnostics,
        snapshot_context: (VisualIndicatorSnapshotContext | None),
    ) -> str:
        """
        Formatea los conteos pertenecientes al snapshot almacenado.
        """

        if snapshot_context is None:
            return (
                "  Auditoría Stoch snapshot: "
                "origen no disponible | "
                "OHLC cerradas="
                f"{diagnostics.source_candle_count} | "
                f"K-periodo={diagnostics.k_period}"
            )

        is_consistent = (
            snapshot_context.ohlc_candle_count == diagnostics.source_candle_count
        )

        consistency_label = "OK" if is_consistent else "REVISAR"

        return (
            "  Auditoría Stoch snapshot: "
            "visibles="
            f"{snapshot_context.visible_candle_count} | "
            "OHLC cerradas="
            f"{snapshot_context.ohlc_candle_count} | "
            f"K-periodo={diagnostics.k_period} | "
            "geometría="
            f"{snapshot_context.geometry_valid_count}/"
            f"{snapshot_context.geometry_total_count} | "
            f"consistencia={consistency_label}"
        )
