from __future__ import annotations

from pocket_option_analyzer.domain.indicators import IndicatorSnapshot
from pocket_option_analyzer.domain.signals import (
    MarketSignal,
    SignalDirection,
    SignalStrength,
)
from pocket_option_analyzer.domain.strategy import StrategyProfile
from pocket_option_analyzer.vision.models import (
    CandleType,
    MarketAnalysis,
    TrendDirection,
)


class StrategyConditionEvaluator:
    """
    Evalúa las condiciones principales de la estrategia OTC Precision 10S.

    Este evaluador no ejecuta operaciones.
    Solo convierte condiciones técnicas en una señal informativa.
    """

    def evaluate(
        self,
        profile: StrategyProfile,
        indicators: IndicatorSnapshot,
        analysis: MarketAnalysis,
    ) -> MarketSignal:

        if self._is_call_setup(
            profile=profile,
            indicators=indicators,
            analysis=analysis,
        ):
            return MarketSignal(
                direction=SignalDirection.CALL,
                strength=SignalStrength.HIGH,
                reason="OTC Precision 10S CALL conditions confirmed.",
            )

        if self._is_put_setup(
            profile=profile,
            indicators=indicators,
            analysis=analysis,
        ):
            return MarketSignal(
                direction=SignalDirection.PUT,
                strength=SignalStrength.HIGH,
                reason="OTC Precision 10S PUT conditions confirmed.",
            )

        return MarketSignal.neutral(
            reason="OTC Precision 10S conditions were not fully confirmed.",
        )

    def _is_call_setup(
        self,
        profile: StrategyProfile,
        indicators: IndicatorSnapshot,
        analysis: MarketAnalysis,
    ) -> bool:

        latest = analysis.series.latest

        if latest is None:
            return False

        return all(
            [
                analysis.trend is TrendDirection.BULLISH,
                indicators.ema.is_bullish_alignment,
                indicators.ema.separation_candles
                >= profile.ema_min_separation_candles,
                indicators.rsi.is_between(
                    profile.rsi_call_min,
                    profile.rsi_call_max,
                ),
                indicators.stochastic.crossed_up,
                indicators.stochastic.k_previous
                <= profile.stoch_call_trigger_max,
                latest.candle_type is CandleType.BULLISH,
            ]
        )

    def _is_put_setup(
        self,
        profile: StrategyProfile,
        indicators: IndicatorSnapshot,
        analysis: MarketAnalysis,
    ) -> bool:

        latest = analysis.series.latest

        if latest is None:
            return False

        return all(
            [
                analysis.trend is TrendDirection.BEARISH,
                indicators.ema.is_bearish_alignment,
                indicators.ema.separation_candles
                >= profile.ema_min_separation_candles,
                indicators.rsi.is_between(
                    profile.rsi_put_min,
                    profile.rsi_put_max,
                ),
                indicators.stochastic.crossed_down,
                indicators.stochastic.k_previous
                >= profile.stoch_put_trigger_min,
                latest.candle_type is CandleType.BEARISH,
            ]
        )