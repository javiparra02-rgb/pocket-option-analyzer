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
from pocket_option_analyzer.presentation.signals import (
    SignalGateAuditPresenter,
)


def _record(
    direction: SignalDirection,
    disposition: SignalRecordDisposition,
    created_second: int,
    interval_second: int,
) -> SignalRecord:

    return SignalRecord(
        signal=MarketSignal(
            direction=direction,
            strength=SignalStrength.HIGH,
            reason="Signal gate audit demonstration.",
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
        source="debug_signal_gate_audit",
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


def main() -> None:

    tracker = SignalGateAuditTracker()
    presenter = SignalGateAuditPresenter()

    records = (
        _record(
            direction=SignalDirection.PUT,
            disposition=(
                SignalRecordDisposition.ACTIONABLE_ACCEPTED
            ),
            created_second=5,
            interval_second=0,
        ),
        _record(
            direction=SignalDirection.PUT,
            disposition=(
                SignalRecordDisposition.DUPLICATE_SUPPRESSED
            ),
            created_second=8,
            interval_second=0,
        ),
        _record(
            direction=SignalDirection.CALL,
            disposition=(
                SignalRecordDisposition.DUPLICATE_SUPPRESSED
            ),
            created_second=12,
            interval_second=0,
        ),
        _record(
            direction=SignalDirection.CALL,
            disposition=(
                SignalRecordDisposition.ACTIONABLE_ACCEPTED
            ),
            created_second=35,
            interval_second=30,
        ),
    )

    print(
        presenter.present(
            tracker.snapshot(),
        ).text
    )

    for record in records:
        snapshot = tracker.track(
            record=record,
        )

        view_model = presenter.present(
            snapshot=snapshot,
        )

        print(
            view_model.text,
        )


if __name__ == "__main__":
    main()