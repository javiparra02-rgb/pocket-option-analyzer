from pocket_option_analyzer.application.signals import StrategySignalGenerator
from pocket_option_analyzer.application.strategy import StrategyConditionEvaluator
from pocket_option_analyzer.domain.indicators import (
    EmaSnapshot,
    IndicatorSnapshot,
    RsiSnapshot,
    StochasticSnapshot,
)
from pocket_option_analyzer.domain.signals import SignalDirection
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


def _analysis(
    trend: TrendDirection,
    candle_type: CandleType,
) -> MarketAnalysis:

    candle = ClassifiedCandle(
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

    return MarketAnalysis(
        series=CandleSeries(
            candles=(candle,),
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


def test_generate_returns_call_when_strategy_conditions_are_confirmed() -> None:

    generator = StrategySignalGenerator(
        profile=StrategyProfile.otc_precision_10s(),
        evaluator=StrategyConditionEvaluator(),
    )

    signal = generator.generate(
        analysis=_analysis(
            trend=TrendDirection.BULLISH,
            candle_type=CandleType.BULLISH,
        ),
        indicators=_call_indicators(),
    )

    assert signal.direction is SignalDirection.CALL


def test_generate_returns_none_when_strategy_conditions_are_not_confirmed() -> None:

    generator = StrategySignalGenerator(
        profile=StrategyProfile.otc_precision_10s(),
        evaluator=StrategyConditionEvaluator(),
    )

    signal = generator.generate(
        analysis=_analysis(
            trend=TrendDirection.SIDEWAYS,
            candle_type=CandleType.BULLISH,
        ),
        indicators=_call_indicators(),
    )

    assert signal.direction is SignalDirection.NONE