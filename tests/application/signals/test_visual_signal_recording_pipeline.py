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
    SignalRecordDisposition,
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


def test_pipeline_suppresses_second_actionable_signal_in_same_candle() -> None:

    history = SignalHistory()
    writer = FakeSignalRecordWriter()

    pipeline = VisualSignalRecordingPipeline(
        analysis_pipeline=(
            FakeVisualStrategySignalAnalysisPipeline()
        ),
        recorder=SignalRecorder(
            history,
        ),
        record_writer=writer,
    )

    first = pipeline.analyze_and_record(
        image=np.zeros(
            (100, 100, 3),
            dtype=np.uint8,
        ),
        created_at=datetime(
            2026,
            7,
            31,
            10,
            30,
            5,
            tzinfo=timezone.utc,
        ),
    )

    duplicate = pipeline.analyze_and_record(
        image=np.zeros(
            (100, 100, 3),
            dtype=np.uint8,
        ),
        created_at=datetime(
            2026,
            7,
            31,
            10,
            30,
            20,
            tzinfo=timezone.utc,
        ),
    )

    assert (
        first.disposition
        is SignalRecordDisposition.ACTIONABLE_ACCEPTED
    )
    assert first.is_actionable is True

    assert (
        duplicate.disposition
        is SignalRecordDisposition.DUPLICATE_SUPPRESSED
    )
    assert duplicate.signal.direction is SignalDirection.CALL
    assert duplicate.is_actionable is False

    assert writer.records == [
        first,
        duplicate,
    ]


def test_pipeline_accepts_same_direction_in_next_candle() -> None:

    pipeline = VisualSignalRecordingPipeline(
        analysis_pipeline=(
            FakeVisualStrategySignalAnalysisPipeline()
        ),
        recorder=SignalRecorder(
            SignalHistory(),
        ),
    )

    first = pipeline.analyze_and_record(
        image=np.zeros(
            (100, 100, 3),
            dtype=np.uint8,
        ),
        created_at=datetime(
            2026,
            7,
            31,
            10,
            30,
            20,
            tzinfo=timezone.utc,
        ),
    )

    second = pipeline.analyze_and_record(
        image=np.zeros(
            (100, 100, 3),
            dtype=np.uint8,
        ),
        created_at=datetime(
            2026,
            7,
            31,
            10,
            30,
            35,
            tzinfo=timezone.utc,
        ),
    )

    assert first.is_actionable is True
    assert second.is_actionable is True