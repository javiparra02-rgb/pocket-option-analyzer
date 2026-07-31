from datetime import datetime, timezone

from pocket_option_analyzer.domain.signals import (
    MarketSignal,
    SignalDirection,
    SignalRecord,
    SignalRecordDisposition,
    SignalStrength,
)


def test_signal_record_exposes_actionable_state() -> None:

    signal = MarketSignal(
        direction=SignalDirection.CALL,
        strength=SignalStrength.HIGH,
        reason="Bullish setup detected.",
    )

    record = SignalRecord(
        signal=signal,
        created_at=datetime(
            2026,
            1,
            1,
            tzinfo=timezone.utc,
        ),
    )

    assert record.is_actionable is True
    assert record.source == "signal_analysis"


def test_duplicate_signal_record_is_not_actionable() -> None:

    interval_started_at = datetime(
        2026,
        7,
        31,
        10,
        30,
        0,
        tzinfo=timezone.utc,
    )

    record = SignalRecord(
        signal=MarketSignal(
            direction=SignalDirection.CALL,
            strength=SignalStrength.HIGH,
            reason="Confirmed.",
        ),
        created_at=datetime(
            2026,
            7,
            31,
            10,
            30,
            12,
            tzinfo=timezone.utc,
        ),
        disposition=(
            SignalRecordDisposition.DUPLICATE_SUPPRESSED
        ),
        candle_interval_started_at=interval_started_at,
    )

    assert record.signal.direction is SignalDirection.CALL
    assert record.is_duplicate_suppressed is True
    assert record.is_actionable is False


def test_accepted_signal_record_remains_actionable() -> None:

    interval_started_at = datetime(
        2026,
        7,
        31,
        10,
        30,
        0,
        tzinfo=timezone.utc,
    )

    record = SignalRecord(
        signal=MarketSignal(
            direction=SignalDirection.PUT,
            strength=SignalStrength.HIGH,
            reason="Confirmed.",
        ),
        created_at=datetime(
            2026,
            7,
            31,
            10,
            30,
            10,
            tzinfo=timezone.utc,
        ),
        disposition=(
            SignalRecordDisposition.ACTIONABLE_ACCEPTED
        ),
        candle_interval_started_at=interval_started_at,
    )

    assert record.is_actionable is True