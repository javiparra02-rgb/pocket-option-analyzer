from __future__ import annotations

from pocket_option_analyzer.application.strategy import (
    StrategyConditionAudit,
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
        self._last_condition_audit: StrategyConditionAudit | None = None

    @property
    def last_condition_audit(self) -> StrategyConditionAudit | None:
        """Audit used to produce the most recent signal, when available."""

        return self._last_condition_audit

    def generate(
        self,
        analysis: MarketAnalysis,
        indicators: IndicatorSnapshot,
    ) -> MarketSignal:
        """
        Genera una señal usando análisis visual + indicadores.
        """

        audit = self._evaluator.audit(
            profile=self._profile,
            indicators=indicators,
            analysis=analysis,
        )
        self._last_condition_audit = audit

        return self._evaluator.evaluate_audit(audit)
