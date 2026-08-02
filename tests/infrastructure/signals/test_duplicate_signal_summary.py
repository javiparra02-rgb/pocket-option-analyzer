from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pocket_option_analyzer.domain.signals import (
    MarketSignal,
    SignalDirection,
    SignalRecord,
    SignalRecordDisposition,
    SignalStrength,
)
from pocket_option_analyzer.infrastructure.signals import (
    DuplicateSignalSummary,
)


def _duplicate(
    direction: SignalDirection,
    created_at: datetime,
    interval_started_at: datetime,
) -> SignalRecord:

    return SignalRecord(
        signal=MarketSignal(
            direction=direction,
            strength=SignalStrength.HIGH,
            reason="Repeated signal.",
        ),
        created_at=created_at,
        source="summary_test",
        disposition=(SignalRecordDisposition.DUPLICATE_SUPPRESSED),
        candle_interval_started_at=interval_started_at,
    )


def test_summary_accumulates_directions_and_timestamps() -> None:

    interval_started_at = datetime(
        2026,
        8,
        1,
        20,
        51,
        30,
        tzinfo=UTC,
    )

    first = _duplicate(
        direction=SignalDirection.CALL,
        created_at=datetime(
            2026,
            8,
            1,
            20,
            51,
            33,
            tzinfo=UTC,
        ),
        interval_started_at=interval_started_at,
    )

    second = _duplicate(
        direction=SignalDirection.PUT,
        created_at=datetime(
            2026,
            8,
            1,
            20,
            51,
            40,
            tzinfo=UTC,
        ),
        interval_started_at=interval_started_at,
    )

    summary = DuplicateSignalSummary.start(
        record=first,
        accepted_direction=SignalDirection.CALL,
        accepted_record_found=True,
    ).add(
        record=second,
    )

    assert summary.duplicate_suppressed_count == 2
    assert summary.call_duplicate_count == 1
    assert summary.put_duplicate_count == 1
    assert summary.first_duplicate_at is first.created_at
    assert summary.last_duplicate_at is second.created_at
    assert summary.accepted_direction is SignalDirection.CALL
    assert summary.accepted_record_found is True


def test_summary_rejects_duplicate_from_another_interval() -> None:

    first_interval = datetime(
        2026,
        8,
        1,
        20,
        51,
        0,
        tzinfo=UTC,
    )

    second_interval = datetime(
        2026,
        8,
        1,
        20,
        51,
        30,
        tzinfo=UTC,
    )

    summary = DuplicateSignalSummary.start(
        record=_duplicate(
            direction=SignalDirection.CALL,
            created_at=datetime(
                2026,
                8,
                1,
                20,
                51,
                5,
                tzinfo=UTC,
            ),
            interval_started_at=first_interval,
        ),
        accepted_direction=SignalDirection.CALL,
        accepted_record_found=True,
    )

    with pytest.raises(
        ValueError,
        match="pertenece a otro intervalo",
    ):
        summary.add(
            record=_duplicate(
                direction=SignalDirection.CALL,
                created_at=datetime(
                    2026,
                    8,
                    1,
                    20,
                    51,
                    35,
                    tzinfo=UTC,
                ),
                interval_started_at=second_interval,
            )
        )
