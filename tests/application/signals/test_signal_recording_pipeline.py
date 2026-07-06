from datetime import datetime, timezone

import numpy as np

from pocket_option_analyzer.application.signals import (
    SignalRecorder,
    SignalRecordingPipeline,
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
    SignalHistory,
    SignalStrength,
)


class FakeStrategySignalAnalysisPipeline:

    def analyze(self, image, indicators):
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


def test_analyze_and_record_adds_generated_signal_to_history() -> None:

    history = SignalHistory()

    pipeline = SignalRecordingPipeline(
        analysis_pipeline=FakeStrategySignalAnalysisPipeline(),
        recorder=SignalRecorder(history),
    )

    created_at = datetime(
        2026,
        1,
        1,
        tzinfo=timezone.utc,
    )

    record = pipeline.analyze_and_record(
        image=np.zeros(
            (100, 100, 3),
            dtype=np.uint8,
        ),
        indicators=_indicators(),
        created_at=created_at,
    )

    assert history.latest() is record
    assert record.signal.direction is SignalDirection.CALL
    assert record.signal.strength is SignalStrength.HIGH
    assert record.created_at is created_at
    assert record.source == "strategy_signal_analysis"