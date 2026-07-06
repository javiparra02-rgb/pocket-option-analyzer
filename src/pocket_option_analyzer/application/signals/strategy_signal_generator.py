from __future__ import annotations

from pocket_option_analyzer.application.strategy import (
    StrategyConditionEvaluator,
)
from pocket_option_analyzer.domain.indicators import IndicatorSnapshot
from pocket_option_analyzer.domain.signals import MarketSignal
from pocket_option_analyzer.domain.strategy import StrategyProfile
from pocket_option_analyzer.vision.models import MarketAnalysis


class StrategySignalGenerator:
    """
    Genera señales usando una estrategia configurada.

    Este generador no ejecuta operaciones.
    Solo devuelve una señal informativa CALL / PUT / NONE.
    """

    def __init__(
        self,
        profile: StrategyProfile,
        evaluator: StrategyConditionEvaluator,
    ) -> None:
        self._profile = profile
        self._evaluator = evaluator

    def generate(
        self,
        analysis: MarketAnalysis,
        indicators: IndicatorSnapshot,
    ) -> MarketSignal:
        """
        Genera una señal usando análisis visual + indicadores.
        """

        return self._evaluator.evaluate(
            profile=self._profile,
            indicators=indicators,
            analysis=analysis,
        )