from pocket_option_analyzer.application.strategy import (
    StrategyConditionEvaluator,
)
from pocket_option_analyzer.domain.indicators import (
    EmaSnapshot,
    IndicatorSnapshot,
    RsiSnapshot,
    StochasticSnapshot,
)
from pocket_option_analyzer.domain.signals import (
    SignalDirection,
    SignalStrength,
)
from pocket_option_analyzer.domain.strategy import StrategyProfile
from pocket_option_analyzer.vision.models import (
    CandleCandidate,
    CandleColor,
    CandleSeries,
    CandleType,
    ClassifiedCandle,
    MarketAnalysis,
    TrendDirection,
)


def _classified_candle(
    candle_type: CandleType,
) -> ClassifiedCandle:

    return ClassifiedCandle(
        candidate=CandleCandidate(
            x=10,
            y=20,
            width=5,
            height=30,
            area=150,
            color=CandleColor.UNKNOWN,
        ),
        candle_type=candle_type,
    )


def _analysis(
    trend: TrendDirection,
    candle_type: CandleType,
) -> MarketAnalysis:

    return MarketAnalysis(
        series=CandleSeries(
            candles=(
                _classified_candle(candle_type),
            ),
        ),
        trend=trend,
    )


def _call_indicators() -> IndicatorSnapshot:

    return IndicatorSnapshot(
        ema=EmaSnapshot(
            fast_value=105.0,
            slow_value=100.0,
            separation_candles=3,
        ),
        rsi=RsiSnapshot(
            value=57.0,
        ),
        stochastic=StochasticSnapshot(
            k_previous=18.0,
            d_previous=20.0,
            k_value=24.0,
            d_value=21.0,
        ),
    )


def _put_indicators() -> IndicatorSnapshot:

    return IndicatorSnapshot(
        ema=EmaSnapshot(
            fast_value=95.0,
            slow_value=100.0,
            separation_candles=3,
        ),
        rsi=RsiSnapshot(
            value=42.0,
        ),
        stochastic=StochasticSnapshot(
            k_previous=82.0,
            d_previous=80.0,
            k_value=76.0,
            d_value=78.0,
        ),
    )


def test_evaluate_returns_call_when_call_conditions_are_confirmed() -> None:

    evaluator = StrategyConditionEvaluator()

    signal = evaluator.evaluate(
        profile=StrategyProfile.otc_precision_10s(),
        indicators=_call_indicators(),
        analysis=_analysis(
            trend=TrendDirection.BULLISH,
            candle_type=CandleType.BULLISH,
        ),
    )

    assert signal.direction is SignalDirection.CALL
    assert signal.strength is SignalStrength.HIGH
    assert signal.is_actionable is True


def test_evaluate_returns_put_when_put_conditions_are_confirmed() -> None:

    evaluator = StrategyConditionEvaluator()

    signal = evaluator.evaluate(
        profile=StrategyProfile.otc_precision_10s(),
        indicators=_put_indicators(),
        analysis=_analysis(
            trend=TrendDirection.BEARISH,
            candle_type=CandleType.BEARISH,
        ),
    )

    assert signal.direction is SignalDirection.PUT
    assert signal.strength is SignalStrength.HIGH
    assert signal.is_actionable is True


def test_evaluate_returns_none_when_conditions_are_not_confirmed() -> None:

    evaluator = StrategyConditionEvaluator()

    signal = evaluator.evaluate(
        profile=StrategyProfile.otc_precision_10s(),
        indicators=_call_indicators(),
        analysis=_analysis(
            trend=TrendDirection.SIDEWAYS,
            candle_type=CandleType.BULLISH,
        ),
    )

    assert signal.direction is SignalDirection.NONE
    assert signal.strength is SignalStrength.NONE
    assert signal.is_actionable is False