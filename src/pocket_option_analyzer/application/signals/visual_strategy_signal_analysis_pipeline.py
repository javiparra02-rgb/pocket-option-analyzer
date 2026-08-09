from __future__ import annotations

import numpy as np

from pocket_option_analyzer.application.market import (
    CandleIntervalIndicatorCacheStatus,
    VisualEntryContextAnalyzer,
    VisualIndicatorSnapshotBuilder,
    VisualIndicatorSnapshotContext,
)
from pocket_option_analyzer.application.signals.strategy_signal_generator import (
    StrategySignalGenerator,
)
from pocket_option_analyzer.application.strategy import (
    DirectionConditionAudit,
    StrategyCondition,
    StrategyConditionAudit,
)
from pocket_option_analyzer.domain.signals import MarketSignal
from pocket_option_analyzer.domain.strategy import StrategyProfile
from pocket_option_analyzer.vision.services import MarketAnalysisPipeline


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

    def analyze(
        self,
        image: np.ndarray,
    ) -> MarketSignal:
        """
        Analiza una imagen y devuelve una señal de mercado.

        El diagnóstico visual se entrega siempre, incluso cuando faltan
        velas para calcular indicadores.
        """

        market_analysis = self._market_analysis_pipeline.analyze(
            image=image,
        )

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
