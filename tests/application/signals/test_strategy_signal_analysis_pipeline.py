import numpy as np

from pocket_option_analyzer.application.signals import (
    StrategySignalAnalysisPipeline,
)
from pocket_option_analyzer.domain.indicators import (
    EmaSnapshot,
    IndicatorSnapshot,
    RsiSnapshot,
    StochasticSnapshot,
)
from pocket_option_analyzer.domain.signals import (
    MarketSignal,
    SignalDirection,
    SignalStrength,
)
from pocket_option_analyzer.vision.models import (
    CandleSeries,
    MarketAnalysis,
    TrendDirection,
)


class FakeMarketAnalysisPipeline:
    def analyze(self, image):
        return MarketAnalysis(
            series=CandleSeries(
                candles=(),
            ),
            trend=TrendDirection.BULLISH,
        )


class FakeStrategySignalGenerator:
    def generate(self, analysis, indicators):
        return MarketSignal(
            direction=SignalDirection.CALL,
            strength=SignalStrength.HIGH,
            reason="Strategy conditions confirmed.",
        )


def _indicators() -> IndicatorSnapshot:

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


def test_analyze_returns_strategy_market_signal() -> None:

    pipeline = StrategySignalAnalysisPipeline(
        market_analysis_pipeline=FakeMarketAnalysisPipeline(),
        signal_generator=FakeStrategySignalGenerator(),
    )

    signal = pipeline.analyze(
        image=np.zeros(
            (100, 100, 3),
            dtype=np.uint8,
        ),
        indicators=_indicators(),
    )

    assert signal.direction is SignalDirection.CALL
    assert signal.strength is SignalStrength.HIGH
    assert signal.is_actionable is True
