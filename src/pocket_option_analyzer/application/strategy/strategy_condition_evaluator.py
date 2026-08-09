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
    ClassifiedCandle,
    MarketAnalysis,
    TrendDirection,
)

from .strategy_condition_audit import (
    DirectionConditionAudit,
    StrategyCondition,
    StrategyConditionAudit,
    StrategyConditionResult,
)


class StrategyConditionEvaluator:
    """
    Evalúa las condiciones de la estrategia OTC Precision 10S.

    No ejecuta operaciones.
    No interactúa con Pocket Option.
    Solo decide si las condiciones visuales e indicadores justifican
    una señal informativa CALL, PUT o NONE.

    En gráficos en vivo, la última vela detectada puede estar formándose.
    Por eso se permite confirmar la dirección usando una ventana reciente
    de velas.
    """

    def __init__(
        self,
        recent_confirmation_candles: int = 3,
        ignore_latest_candle: bool = True,
    ) -> None:
        self._recent_confirmation_candles = recent_confirmation_candles
        self._ignore_latest_candle = ignore_latest_candle

    def evaluate(
        self,
        profile: StrategyProfile,
        indicators: IndicatorSnapshot,
        analysis: MarketAnalysis,
    ) -> MarketSignal:

        audit = self.audit(
            profile=profile,
            indicators=indicators,
            analysis=analysis,
        )

        return self.evaluate_audit(audit)

    def evaluate_audit(
        self,
        audit: StrategyConditionAudit,
    ) -> MarketSignal:
        """Build the STRICT signal from an already calculated audit."""

        if audit.call.is_confirmed:
            return MarketSignal(
                direction=SignalDirection.CALL,
                strength=SignalStrength.HIGH,
                reason="OTC Precision 10S CALL setup confirmed.",
            )

        if audit.put.is_confirmed:
            return MarketSignal(
                direction=SignalDirection.PUT,
                strength=SignalStrength.HIGH,
                reason="OTC Precision 10S PUT setup confirmed.",
            )

        return MarketSignal.neutral(
            reason=self._neutral_reason(
                call_failures=list(audit.call.failures),
                put_failures=list(audit.put.failures),
            ),
        )

    def audit(
        self,
        profile: StrategyProfile,
        indicators: IndicatorSnapshot,
        analysis: MarketAnalysis,
    ) -> StrategyConditionAudit:
        """Return all seven outcomes for CALL and PUT without changing STRICT."""

        separation_ok = (
            indicators.ema.separation_candles >= profile.ema_min_separation_candles
        )

        return StrategyConditionAudit(
            call=DirectionConditionAudit(
                direction=SignalDirection.CALL,
                conditions=(
                    self._result(
                        StrategyCondition.TREND,
                        analysis.trend is TrendDirection.BULLISH,
                        "trend is not bullish",
                    ),
                    self._result(
                        StrategyCondition.EMA_ALIGNMENT,
                        indicators.ema.is_bullish_alignment,
                        "EMA alignment is not bullish",
                    ),
                    self._result(
                        StrategyCondition.EMA_SEPARATION,
                        separation_ok,
                        "EMA separation is insufficient",
                    ),
                    self._result(
                        StrategyCondition.RSI_RANGE,
                        indicators.rsi.is_between(
                            profile.rsi_call_min, profile.rsi_call_max
                        ),
                        "RSI is not in CALL range",
                    ),
                    self._result(
                        StrategyCondition.STOCHASTIC_CROSS,
                        indicators.stochastic.crossed_up,
                        "stochastic did not cross up",
                    ),
                    self._result(
                        StrategyCondition.STOCHASTIC_TRIGGER_ZONE,
                        indicators.stochastic.k_previous
                        <= profile.stoch_call_trigger_max,
                        "stochastic previous K is above CALL trigger zone",
                    ),
                    self._result(
                        StrategyCondition.RECENT_CANDLE_CONFIRMATION,
                        self._has_recent_candle_type(analysis, CandleType.BULLISH),
                        "recent closed candle is not bullish",
                    ),
                ),
            ),
            put=DirectionConditionAudit(
                direction=SignalDirection.PUT,
                conditions=(
                    self._result(
                        StrategyCondition.TREND,
                        analysis.trend is TrendDirection.BEARISH,
                        "trend is not bearish",
                    ),
                    self._result(
                        StrategyCondition.EMA_ALIGNMENT,
                        indicators.ema.is_bearish_alignment,
                        "EMA alignment is not bearish",
                    ),
                    self._result(
                        StrategyCondition.EMA_SEPARATION,
                        separation_ok,
                        "EMA separation is insufficient",
                    ),
                    self._result(
                        StrategyCondition.RSI_RANGE,
                        indicators.rsi.is_between(
                            profile.rsi_put_min, profile.rsi_put_max
                        ),
                        "RSI is not in PUT range",
                    ),
                    self._result(
                        StrategyCondition.STOCHASTIC_CROSS,
                        indicators.stochastic.crossed_down,
                        "stochastic did not cross down",
                    ),
                    self._result(
                        StrategyCondition.STOCHASTIC_TRIGGER_ZONE,
                        indicators.stochastic.k_previous
                        >= profile.stoch_put_trigger_min,
                        "stochastic previous K is below PUT trigger zone",
                    ),
                    self._result(
                        StrategyCondition.RECENT_CANDLE_CONFIRMATION,
                        self._has_recent_candle_type(analysis, CandleType.BEARISH),
                        "recent closed candle is not bearish",
                    ),
                ),
            ),
        )

    @staticmethod
    def _result(
        condition: StrategyCondition,
        passed: bool,
        failure_reason: str,
    ) -> StrategyConditionResult:
        return StrategyConditionResult(
            condition=condition,
            passed=passed,
            failure_reason=None if passed else failure_reason,
        )

    def _has_recent_candle_type(
        self,
        analysis: MarketAnalysis,
        candle_type: CandleType,
    ) -> bool:

        recent_candles = self._recent_candles(
            analysis=analysis,
        )

        return any(candle.candle_type is candle_type for candle in recent_candles)

    def _recent_candles(
        self,
        analysis: MarketAnalysis,
    ) -> tuple[ClassifiedCandle, ...]:

        candles = tuple(
            analysis.series.candles,
        )

        if self._ignore_latest_candle and len(candles) > 1:
            candles = candles[:-1]

        directional_candles = tuple(
            candle
            for candle in candles
            if candle.candle_type
            in {
                CandleType.BULLISH,
                CandleType.BEARISH,
            }
        )

        return tuple(directional_candles[-self._recent_confirmation_candles :])

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
