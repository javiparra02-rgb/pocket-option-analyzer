from datetime import UTC, datetime

from pocket_option_analyzer.application.signals import SignalRecorder
from pocket_option_analyzer.domain.signals import (
    MarketSignal,
    SignalDirection,
    SignalHistory,
    SignalStrength,
)


def test_record_adds_signal_to_history() -> None:

    history = SignalHistory()
    recorder = SignalRecorder(history)

    signal = MarketSignal(
        direction=SignalDirection.CALL,
        strength=SignalStrength.HIGH,
        reason="Strategy conditions confirmed.",
    )

    created_at = datetime(
        2026,
        1,
        1,
        tzinfo=UTC,
    )

    record = recorder.record(
        signal=signal,
        created_at=created_at,
    )

    assert history.latest() is record
    assert record.signal is signal
    assert record.created_at is created_at
    assert record.source == "strategy_signal_analysis"


def test_record_preserves_custom_source() -> None:

    history = SignalHistory()
    recorder = SignalRecorder(history)

    signal = MarketSignal.neutral(
        reason="No confirmed setup.",
    )

    record = recorder.record(
        signal=signal,
        source="manual_test",
    )

    assert history.latest() is record
    assert record.source == "manual_test"
    assert record.is_actionable is False
