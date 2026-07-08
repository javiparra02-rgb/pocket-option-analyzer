from pocket_option_analyzer.application.strategy import (
    StrategyConditionEvaluator,
)
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
            y=10,
            width=5,
            height=20,
            area=100,
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
                _classified_candle(
                    candle_type=candle_type,
                ),
            ),
        ),
        trend=trend,
    )


def test_evaluator_returns_call_when_all_call_conditions_match() -> None:

    evaluator = StrategyConditionEvaluator()

    signal = evaluator.evaluate(
        profile=StrategyProfile.otc_precision_10s(),
        indicators=IndicatorSnapshot(
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
        ),
        analysis=_analysis(
            trend=TrendDirection.BULLISH,
            candle_type=CandleType.BULLISH,
        ),
    )

    assert signal.direction is SignalDirection.CALL
    assert signal.reason == "OTC Precision 10S CALL setup confirmed."


def test_evaluator_returns_put_when_all_put_conditions_match() -> None:

    evaluator = StrategyConditionEvaluator()

    signal = evaluator.evaluate(
        profile=StrategyProfile.otc_precision_10s(),
        indicators=IndicatorSnapshot(
            ema=EmaSnapshot(
                fast_value=100.0,
                slow_value=105.0,
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
        ),
        analysis=_analysis(
            trend=TrendDirection.BEARISH,
            candle_type=CandleType.BEARISH,
        ),
    )

    assert signal.direction is SignalDirection.PUT
    assert signal.reason == "OTC Precision 10S PUT setup confirmed."


def test_evaluator_returns_neutral_with_diagnostics_when_conditions_do_not_match() -> None:

    evaluator = StrategyConditionEvaluator()

    signal = evaluator.evaluate(
        profile=StrategyProfile.otc_precision_10s(),
        indicators=IndicatorSnapshot(
            ema=EmaSnapshot(
                fast_value=100.0,
                slow_value=100.0,
                separation_candles=0,
            ),
            rsi=RsiSnapshot(
                value=50.0,
            ),
            stochastic=StochasticSnapshot(
                k_previous=50.0,
                d_previous=50.0,
                k_value=50.0,
                d_value=50.0,
            ),
        ),
        analysis=_analysis(
            trend=TrendDirection.SIDEWAYS,
            candle_type=CandleType.DOJI,
        ),
    )

    assert signal.direction is SignalDirection.NONE
    assert signal.is_actionable is False
    assert signal.reason.startswith(
        "OTC Precision 10S conditions were not fully confirmed."
    )
    assert "CALL failed:" in signal.reason
    assert "PUT failed:" in signal.reason
    assert "trend is not bullish" in signal.reason
    assert "trend is not bearish" in signal.reason