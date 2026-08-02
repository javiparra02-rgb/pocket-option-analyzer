from __future__ import annotations

import numpy as np

from pocket_option_analyzer.application.signals.strategy_signal_generator import (
    StrategySignalGenerator,
)
from pocket_option_analyzer.domain.indicators import IndicatorSnapshot
from pocket_option_analyzer.domain.signals import MarketSignal
from pocket_option_analyzer.vision.services import MarketAnalysisPipeline


class StrategySignalAnalysisPipeline:
    """
    Pipeline de aplicación que genera señales usando la estrategia completa.

    Combina:
    - análisis visual del gráfico
    - estado de indicadores técnicos
    - reglas de la estrategia configurada

    Este pipeline no ejecuta operaciones.
    Solo devuelve una señal informativa CALL / PUT / NONE.
    """

    def __init__(
        self,
        market_analysis_pipeline: MarketAnalysisPipeline,
        signal_generator: StrategySignalGenerator,
    ) -> None:
        self._market_analysis_pipeline = market_analysis_pipeline
        self._signal_generator = signal_generator

    def analyze(
        self,
        image: np.ndarray,
        indicators: IndicatorSnapshot,
    ) -> MarketSignal:
        """
        Analiza imagen + indicadores y devuelve una señal de mercado.
        """

        market_analysis = self._market_analysis_pipeline.analyze(image)

        return self._signal_generator.generate(
            analysis=market_analysis,
            indicators=indicators,
        )
