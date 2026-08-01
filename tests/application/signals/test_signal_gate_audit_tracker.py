from __future__ import annotations

from datetime import datetime, timezone

from pocket_option_analyzer.application.signals import (
    SignalGateAuditTracker,
)
from pocket_option_analyzer.domain.signals import (
    MarketSignal,
    SignalDirection,
    SignalRecord,
    SignalRecordDisposition,
    SignalStrength,
)


def _actionable_record(
    disposition: SignalRecordDisposition,
    direction: SignalDirection = SignalDirection.CALL,
    created_second: int = 5,
    interval_second: int = 0,
) -> SignalRecord:

    return SignalRecord(
        signal=MarketSignal(
            direction=direction,
            strength=SignalStrength.HIGH,
            reason="Test signal.",
        ),
        created_at=datetime(
            2026,
            7,
            31,
            10,
            30,
            created_second,
            tzinfo=timezone.utc,
        ),
        disposition=disposition,
        candle_interval_started_at=datetime(
            2026,
            7,
            31,
            10,
            30,
            interval_second,
            tzinfo=timezone.utc,
        ),
    )


def test_tracker_ignores_observed_record() -> None:

    tracker = SignalGateAuditTracker()

    tracker.track(
        SignalRecord(
            signal=MarketSignal.neutral(
                reason="Waiting.",
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
    )

    snapshot = tracker.snapshot()

    assert snapshot.accepted_count == 0
    assert snapshot.duplicate_suppressed_count == 0
    assert snapshot.last_disposition is None


def test_tracker_counts_accepted_signal() -> None:

    tracker = SignalGateAuditTracker()

    snapshot = tracker.track(
        _actionable_record(
            disposition=(
                SignalRecordDisposition.ACTIONABLE_ACCEPTED
            ),
            direction=SignalDirection.PUT,
        )
    )

    assert snapshot.accepted_count == 1
    assert snapshot.duplicate_suppressed_count == 0
    assert (
        snapshot.last_disposition
        is SignalRecordDisposition.ACTIONABLE_ACCEPTED
    )
    assert snapshot.last_direction is SignalDirection.PUT


def test_tracker_counts_duplicate_without_adding_accepted_signal() -> None:

    tracker = SignalGateAuditTracker()

    tracker.track(
        _actionable_record(
            disposition=(
                SignalRecordDisposition.ACTIONABLE_ACCEPTED
            ),
        )
    )

    snapshot = tracker.track(
        _actionable_record(
            disposition=(
                SignalRecordDisposition.DUPLICATE_SUPPRESSED
            ),
            direction=SignalDirection.PUT,
            created_second=12,
        )
    )

    assert snapshot.accepted_count == 1
    assert snapshot.duplicate_suppressed_count == 1
    assert (
        snapshot.last_disposition
        is SignalRecordDisposition.DUPLICATE_SUPPRESSED
    )
    assert snapshot.last_direction is SignalDirection.PUT


def test_tracker_reset_clears_execution_audit() -> None:

    tracker = SignalGateAuditTracker()

    tracker.track(
        _actionable_record(
            disposition=(
                SignalRecordDisposition.ACTIONABLE_ACCEPTED
            ),
        )
    )

    tracker.reset()

    snapshot = tracker.snapshot()

    assert snapshot.accepted_count == 0
    assert snapshot.duplicate_suppressed_count == 0
    assert snapshot.last_disposition is None