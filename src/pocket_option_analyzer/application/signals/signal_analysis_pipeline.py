from __future__ import annotations

import numpy as np

from pocket_option_analyzer.application.signals.trend_signal_generator import (
    TrendSignalGenerator,
)
from pocket_option_analyzer.domain.signals import MarketSignal
from pocket_option_analyzer.vision.services import MarketAnalysisPipeline


class SignalAnalysisPipeline:
    """
    Pipeline de aplicación encargado de convertir una imagen del gráfico
    en una señal de mercado.

    Flujo:
    - analiza visualmente el mercado
    - detecta tendencia
    - genera una señal CALL / PUT / NONE

    Este pipeline no ejecuta operaciones.
    Solo devuelve una señal informativa.
    """

    def __init__(
        self,
        market_analysis_pipeline: MarketAnalysisPipeline,
        signal_generator: TrendSignalGenerator,
    ) -> None:
        self._market_analysis_pipeline = market_analysis_pipeline
        self._signal_generator = signal_generator

    def analyze(
        self,
        image: np.ndarray,
    ) -> MarketSignal:
        """
        Analiza una imagen del gráfico y devuelve una señal.
        """

        market_analysis = self._market_analysis_pipeline.analyze(image)

        return self._signal_generator.generate(market_analysis)
