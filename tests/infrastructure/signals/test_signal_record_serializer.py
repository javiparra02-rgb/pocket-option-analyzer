from datetime import datetime, timezone

from pocket_option_analyzer.domain.signals import (
    MarketSignal,
    SignalDirection,
    SignalRecord,
    SignalRecordDisposition,
    SignalStrength,
)
from pocket_option_analyzer.infrastructure.signals import (
    DuplicateSignalSummary,
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


def test_serializer_creates_duplicate_summary_record() -> None:

    interval_started_at = datetime(
        2026,
        8,
        1,
        20,
        51,
        30,
        tzinfo=timezone.utc,
    )

    first_duplicate = SignalRecord(
        signal=MarketSignal(
            direction=SignalDirection.CALL,
            strength=SignalStrength.HIGH,
            reason="Repeated diagnostics.",
        ),
        created_at=datetime(
            2026,
            8,
            1,
            20,
            51,
            33,
            tzinfo=timezone.utc,
        ),
        source="serializer_test",
        disposition=(
            SignalRecordDisposition.DUPLICATE_SUPPRESSED
        ),
        candle_interval_started_at=interval_started_at,
    )

    summary = DuplicateSignalSummary.start(
        record=first_duplicate,
        accepted_direction=SignalDirection.CALL,
        accepted_record_found=True,
    )

    data = (
        SignalRecordSerializer()
        .to_duplicate_summary_dict(
            summary=summary,
        )
    )

    assert data == {
        "event_type": "duplicate_signal_summary",
        "created_at": "2026-08-01T20:51:33+00:00",
        "candle_interval_started_at": (
            "2026-08-01T20:51:30+00:00"
        ),
        "source": "serializer_test",
        "accepted_direction": "call",
        "accepted_record_found": True,
        "disposition": "duplicate_suppressed",
        "duplicate_suppressed_count": 1,
        "duplicate_direction_counts": {
            "call": 1,
            "put": 0,
        },
        "first_duplicate_at": (
            "2026-08-01T20:51:33+00:00"
        ),
        "last_duplicate_at": (
            "2026-08-01T20:51:33+00:00"
        ),
        "is_actionable": False,
        "is_duplicate_suppressed": True,
        "storage_format": "summary",
    }

    assert "reason" not in data