from datetime import datetime, timezone

from pocket_option_analyzer.domain.signals import (
    MarketSignal,
    SignalDirection,
    SignalRecord,
    SignalRecordDisposition,
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
        "storage_format": "full",
    }


def test_serializer_creates_compact_duplicate_record() -> None:

    interval_started_at = datetime(
        2026,
        8,
        1,
        20,
        51,
        30,
        tzinfo=timezone.utc,
    )

    record = SignalRecord(
        signal=MarketSignal(
            direction=SignalDirection.CALL,
            strength=SignalStrength.HIGH,
            reason=(
                "Este diagnóstico sería deliberadamente "
                "muy extenso."
            ),
        ),
        created_at=datetime(
            2026,
            8,
            1,
            20,
            51,
            40,
            tzinfo=timezone.utc,
        ),
        source="serializer_test",
        disposition=(
            SignalRecordDisposition.DUPLICATE_SUPPRESSED
        ),
        candle_interval_started_at=interval_started_at,
    )

    data = SignalRecordSerializer().to_compact_dict(
        record=record,
    )

    assert data == {
        "created_at": "2026-08-01T20:51:40+00:00",
        "candle_interval_started_at": (
            "2026-08-01T20:51:30+00:00"
        ),
        "source": "serializer_test",
        "direction": "call",
        "strength": "high",
        "disposition": "duplicate_suppressed",
        "is_actionable": False,
        "is_duplicate_suppressed": True,
        "storage_format": "compact",
    }

    assert "reason" not in data