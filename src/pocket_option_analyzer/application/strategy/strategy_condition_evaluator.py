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
    Evalúa las condiciones de la estrategia OTC Precision 10S.

    No ejecuta operaciones.
    No interactúa con Pocket Option.
    Solo decide si las condiciones visuales e indicadores justifican
    una señal informativa CALL, PUT o NONE.
    """

    def evaluate(
        self,
        profile: StrategyProfile,
        indicators: IndicatorSnapshot,
        analysis: MarketAnalysis,
    ) -> MarketSignal:

        call_failures = self._call_failures(
            profile=profile,
            indicators=indicators,
            analysis=analysis,
        )

        if not call_failures:
            return MarketSignal(
                direction=SignalDirection.CALL,
                strength=SignalStrength.HIGH,
                reason="OTC Precision 10S CALL setup confirmed.",
            )

        put_failures = self._put_failures(
            profile=profile,
            indicators=indicators,
            analysis=analysis,
        )

        if not put_failures:
            return MarketSignal(
                direction=SignalDirection.PUT,
                strength=SignalStrength.HIGH,
                reason="OTC Precision 10S PUT setup confirmed.",
            )

        return MarketSignal.neutral(
            reason=self._neutral_reason(
                call_failures=call_failures,
                put_failures=put_failures,
            ),
        )

    def _call_failures(
        self,
        profile: StrategyProfile,
        indicators: IndicatorSnapshot,
        analysis: MarketAnalysis,
    ) -> list[str]:

        failures: list[str] = []

        if analysis.trend is not TrendDirection.BULLISH:
            failures.append(
                "trend is not bullish",
            )

        if not indicators.ema.is_bullish_alignment:
            failures.append(
                "EMA alignment is not bullish",
            )

        if (
            indicators.ema.separation_candles
            < profile.ema_min_separation_candles
        ):
            failures.append(
                "EMA separation is insufficient",
            )

        if not indicators.rsi.is_between(
            profile.rsi_call_min,
            profile.rsi_call_max,
        ):
            failures.append(
                "RSI is not in CALL range",
            )

        if not indicators.stochastic.crossed_up:
            failures.append(
                "stochastic did not cross up",
            )

        if indicators.stochastic.k_previous > profile.stoch_call_trigger_max:
            failures.append(
                "stochastic previous K is above CALL trigger zone",
            )

        latest = analysis.series.latest

        if latest is None or latest.candle_type is not CandleType.BULLISH:
            failures.append(
                "latest candle is not bullish",
            )

        return failures

    def _put_failures(
        self,
        profile: StrategyProfile,
        indicators: IndicatorSnapshot,
        analysis: MarketAnalysis,
    ) -> list[str]:

        failures: list[str] = []

        if analysis.trend is not TrendDirection.BEARISH:
            failures.append(
                "trend is not bearish",
            )

        if not indicators.ema.is_bearish_alignment:
            failures.append(
                "EMA alignment is not bearish",
            )

        if (
            indicators.ema.separation_candles
            < profile.ema_min_separation_candles
        ):
            failures.append(
                "EMA separation is insufficient",
            )

        if not indicators.rsi.is_between(
            profile.rsi_put_min,
            profile.rsi_put_max,
        ):
            failures.append(
                "RSI is not in PUT range",
            )

        if not indicators.stochastic.crossed_down:
            failures.append(
                "stochastic did not cross down",
            )

        if indicators.stochastic.k_previous < profile.stoch_put_trigger_min:
            failures.append(
                "stochastic previous K is below PUT trigger zone",
            )

        latest = analysis.series.latest

        if latest is None or latest.candle_type is not CandleType.BEARISH:
            failures.append(
                "latest candle is not bearish",
            )

        return failures

    def _neutral_reason(
        self,
        call_failures: list[str],
        put_failures: list[str],
    ) -> str:

        return (
            "OTC Precision 10S conditions were not fully confirmed. "
            f"CALL failed: {self._format_failures(call_failures)}. "
            f"PUT failed: {self._format_failures(put_failures)}."
        )

    def _format_failures(
        self,
        failures: list[str],
    ) -> str:

        if not failures:
            return "none"

        return ", ".join(
            failures,
        )