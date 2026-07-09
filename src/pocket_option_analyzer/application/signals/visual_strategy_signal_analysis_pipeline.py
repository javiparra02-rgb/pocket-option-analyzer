from __future__ import annotations

import numpy as np

from pocket_option_analyzer.application.market import (
    VisualIndicatorSnapshotBuilder,
)
from pocket_option_analyzer.application.signals.strategy_signal_generator import (
    StrategySignalGenerator,
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
    ) -> None:
        self._market_analysis_pipeline = market_analysis_pipeline
        self._indicator_snapshot_builder = indicator_snapshot_builder
        self._signal_generator = signal_generator
        self._profile = profile

    def analyze(
        self,
        image: np.ndarray,
    ) -> MarketSignal:
        """
        Analiza una imagen y devuelve una señal de mercado.

        Si no hay suficientes velas para calcular indicadores,
        devuelve una señal neutral con diagnóstico.
        """

        market_analysis = self._market_analysis_pipeline.analyze(
            image=image,
        )

        indicators = self._indicator_snapshot_builder.build(
            series=market_analysis.series,
            profile=self._profile,
        )

        if indicators is None:
            return MarketSignal.neutral(
                reason=self._not_enough_candles_reason(
                    detected_candles=len(
                        market_analysis.series,
                    ),
                ),
            )

        signal = self._signal_generator.generate(
            analysis=market_analysis,
            indicators=indicators,
        )

        return MarketSignal(
            direction=signal.direction,
            strength=signal.strength,
            reason=(
                f"{self._visual_diagnostics_line(market_analysis)}\n"
                f"{signal.reason}"
            ),
        )

    def _not_enough_candles_reason(
        self,
        detected_candles: int,
    ) -> str:
        return (
            "Not enough visual candles to calculate indicators. "
            f"Detected candles: {detected_candles}. "
            f"Minimum required: {self._minimum_required_candles()}."
        )

    def _minimum_required_candles(
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
    ) -> str:

        candles = tuple(
            market_analysis.series.candles,
        )

        latest_candles = candles[-3:]

        closed_candles = (
            candles[:-1]
            if len(candles) > 1
            else candles
        )

        recent_closed_candles = closed_candles[-3:]

        latest_text = self._candle_types_text(
            latest_candles,
        )
        recent_closed_text = self._candle_types_text(
            recent_closed_candles,
        )

        return (
            "[visual_diagnostics] "
            f"Diagnóstico visual: Tendencia: {market_analysis.trend.name} | "
            f"Velas: {len(market_analysis.series)} | "
            f"Últimas: {latest_text} | "
            f"Cerradas: {recent_closed_text}"
        )


    def _candle_types_text(
        self,
        candles,
    ) -> str:

        labels = [
            candle.candle_type.name
            for candle in candles
        ]

        return (
            ", ".join(
                labels,
            )
            if labels
            else "NONE"
        )