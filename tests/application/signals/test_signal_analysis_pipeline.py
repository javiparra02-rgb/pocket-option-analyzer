import numpy as np

from pocket_option_analyzer.application.signals import (
    SignalAnalysisPipeline,
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


class FakeSignalGenerator:
    def generate(self, analysis):
        return MarketSignal(
            direction=SignalDirection.CALL,
            strength=SignalStrength.MEDIUM,
            reason="Bullish trend detected.",
        )


def test_analyze_returns_market_signal() -> None:

    pipeline = SignalAnalysisPipeline(
        market_analysis_pipeline=FakeMarketAnalysisPipeline(),
        signal_generator=FakeSignalGenerator(),
    )

    signal = pipeline.analyze(
        np.zeros(
            (100, 100, 3),
            dtype=np.uint8,
        )
    )

    assert signal.direction is SignalDirection.CALL
    assert signal.strength is SignalStrength.MEDIUM
    assert signal.is_actionable is True
