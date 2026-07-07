from datetime import datetime, timezone

import numpy as np

from pocket_option_analyzer.application.signals import (
    SignalRecorder,
    VisualSignalRecordingPipeline,
)
from pocket_option_analyzer.domain.signals import (
    MarketSignal,
    SignalDirection,
    SignalHistory,
    SignalRecord,
    SignalStrength,
)


class FakeVisualStrategySignalAnalysisPipeline:

    def analyze(
        self,
        image,
    ) -> MarketSignal:
        return MarketSignal(
            direction=SignalDirection.CALL,
            strength=SignalStrength.HIGH,
            reason="Visual strategy conditions confirmed.",
        )


class FakeSignalRecordWriter:

    def __init__(self) -> None:
        self.records: list[SignalRecord] = []

    def write(
        self,
        record: SignalRecord,
    ) -> None:
        self.records.append(record)


def test_analyze_and_record_adds_visual_signal_to_history() -> None:

    history = SignalHistory()

    pipeline = VisualSignalRecordingPipeline(
        analysis_pipeline=FakeVisualStrategySignalAnalysisPipeline(),
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
        created_at=created_at,
    )

    assert history.latest() is record
    assert record.signal.direction is SignalDirection.CALL
    assert record.signal.strength is SignalStrength.HIGH
    assert record.signal.reason == "Visual strategy conditions confirmed."
    assert record.created_at is created_at
    assert record.source == "visual_strategy_signal_analysis"


def test_analyze_and_record_writes_visual_signal_when_writer_is_configured() -> None:

    history = SignalHistory()
    writer = FakeSignalRecordWriter()

    pipeline = VisualSignalRecordingPipeline(
        analysis_pipeline=FakeVisualStrategySignalAnalysisPipeline(),
        recorder=SignalRecorder(history),
        record_writer=writer,
    )

    record = pipeline.analyze_and_record(
        image=np.zeros(
            (100, 100, 3),
            dtype=np.uint8,
        ),
    )

    assert history.latest() is record
    assert writer.records == [
        record,
    ]