from __future__ import annotations

from pocket_option_analyzer.domain.signals import (
    MarketSignal,
    SignalDirection,
    SignalStrength,
)
from pocket_option_analyzer.vision.models import (
    MarketAnalysis,
    TrendDirection,
)


class TrendSignalGenerator:
    """
    Genera una señal básica usando únicamente la tendencia detectada.

    Esta versión es conservadora:
    - tendencia bullish -> CALL con fuerza media
    - tendencia bearish -> PUT con fuerza media
    - sideways/unknown -> NONE

    El programa solo informa señales.
    Nunca ejecuta operaciones automáticamente.
    """

    def generate(
        self,
        analysis: MarketAnalysis,
    ) -> MarketSignal:

        if analysis.trend is TrendDirection.BULLISH:
            return MarketSignal(
                direction=SignalDirection.CALL,
                strength=SignalStrength.MEDIUM,
                reason="Bullish trend detected.",
            )

        if analysis.trend is TrendDirection.BEARISH:
            return MarketSignal(
                direction=SignalDirection.PUT,
                strength=SignalStrength.MEDIUM,
                reason="Bearish trend detected.",
            )

        return MarketSignal.neutral(
            reason="No clear directional trend detected.",
        )
