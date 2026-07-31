from datetime import datetime, timezone

from pocket_option_analyzer.domain.signals import (
    MarketSignal,
    SignalDirection,
    SignalRecord,
    SignalStrength,
)
from pocket_option_analyzer.infrastructure.signals import (
    SignalRecordSerializer,
)


def test_signal_record_serializer_converts_record_to_dict() -> None:

    signal = MarketSignal(
        direction=SignalDirection.CALL,
        strength=SignalStrength.HIGH,
        reason="Strategy conditions confirmed.",
    )

    record = SignalRecord(
        signal=signal,
        created_at=datetime(
            2026,
            1,
            1,
            tzinfo=timezone.utc,
        ),
        source="test_source",
    )

    serializer = SignalRecordSerializer()

    data = serializer.to_dict(record)

    assert data == {
        "created_at": "2026-01-01T00:00:00+00:00",
        "candle_interval_started_at": None,
        "source": "test_source",
        "direction": "call",
        "strength": "high",
        "reason": "Strategy conditions confirmed.",
        "disposition": "observed",
        "is_actionable": True,
        "is_duplicate_suppressed": False,
    }