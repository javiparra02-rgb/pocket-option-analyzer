from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from pocket_option_analyzer.application.session_results import (
    ManualSignalResultSessionService,
)
from pocket_option_analyzer.domain.session_results import (
    ManualSignalResult,
    ManualSignalResultEventType,
)
from pocket_option_analyzer.domain.signals import (
    MarketSignal,
    SignalDirection,
    SignalRecord,
    SignalStrength,
)


class FakeWriter:

    def __init__(
        self,
        error: Exception | None = None,
    ) -> None:
        self.records = []
        self.error = error

    def append(
        self,
        record,
    ) -> None:
        if self.error is not None:
            raise self.error

        self.records.append(
            record,
        )


def _signal_record(
    direction: SignalDirection = SignalDirection.CALL,
    second: int = 0,
    created_at: datetime | None = None,
) -> SignalRecord:
    return SignalRecord(
        signal=MarketSignal(
            direction=direction,
            strength=SignalStrength.HIGH,
            reason=f"{direction.value} confirmed.",
        ),
        created_at=(
            created_at
            if created_at is not None
            else datetime(
                2026,
                7,
                21,
                10,
                0,
                second,
                tzinfo=timezone.utc,
            )
        ),
        source="test_source",
    )


def _clock() -> datetime:
    return datetime(
        2026,
        7,
        21,
        10,
        1,
        0,
        tzinfo=timezone.utc,
    )


def test_manual_result_session_starts_empty() -> None:
    service = ManualSignalResultSessionService(
        writer=FakeWriter(),
    )

    assert service.pending_count == 0
    assert service.recorded_count == 0


def test_manual_result_session_tracks_and_registers_result() -> None:
    writer = FakeWriter()
    service = ManualSignalResultSessionService(
        writer=writer,
        clock=_clock,
        event_id_factory=lambda: "event-001",
    )

    signal = _signal_record()

    assert service.track_confirmed_signal(signal) is True

    record = service.register_result(
        ManualSignalResult.WIN,
    )

    assert record is not None
    assert record.event_id == "event-001"
    assert record.result == ManualSignalResult.WIN
    assert record.direction == SignalDirection.CALL
    assert service.pending_count == 0
    assert service.recorded_count == 1
    assert writer.records == [
        record,
    ]


def test_manual_result_session_uses_fifo_signal_order() -> None:
    writer = FakeWriter()
    service = ManualSignalResultSessionService(
        writer=writer,
        clock=_clock,
        event_id_factory=lambda: f"event-{len(writer.records) + 1}",
    )

    first = _signal_record(
        direction=SignalDirection.CALL,
        second=1,
    )
    second = _signal_record(
        direction=SignalDirection.PUT,
        second=2,
    )

    service.track_confirmed_signal(first)
    service.track_confirmed_signal(second)

    first_result = service.register_result(
        ManualSignalResult.WIN,
    )
    second_result = service.register_result(
        ManualSignalResult.LOSS,
    )

    assert first_result is not None
    assert second_result is not None
    assert first_result.direction == SignalDirection.CALL
    assert second_result.direction == SignalDirection.PUT


def test_manual_result_session_returns_none_without_pending_signal() -> None:
    service = ManualSignalResultSessionService(
        writer=FakeWriter(),
    )

    assert (
        service.register_result(
            ManualSignalResult.WIN,
        )
        is None
    )


def test_manual_result_session_undo_writes_reversal() -> None:
    ids = iter(
        [
            "original-001",
            "reversal-001",
        ]
    )
    writer = FakeWriter()
    service = ManualSignalResultSessionService(
        writer=writer,
        clock=_clock,
        event_id_factory=lambda: next(ids),
    )

    service.track_confirmed_signal(
        _signal_record(),
    )
    original = service.register_result(
        ManualSignalResult.LOSS,
    )
    reversal = service.undo_last_result()

    assert original is not None
    assert reversal is not None
    assert reversal.event_type == ManualSignalResultEventType.REVERSED
    assert reversal.reverses_event_id == original.event_id
    assert service.pending_count == 1
    assert service.recorded_count == 0
    assert len(writer.records) == 2


def test_manual_result_session_reset_clears_only_memory() -> None:
    writer = FakeWriter()
    service = ManualSignalResultSessionService(
        writer=writer,
        clock=_clock,
        event_id_factory=lambda: "event-001",
    )

    service.track_confirmed_signal(
        _signal_record(),
    )
    service.register_result(
        ManualSignalResult.WIN,
    )

    service.reset()

    assert service.pending_count == 0
    assert service.recorded_count == 0
    assert len(writer.records) == 1


def test_manual_result_session_does_not_consume_signal_when_writer_fails() -> None:
    service = ManualSignalResultSessionService(
        writer=FakeWriter(
            error=OSError("disk unavailable"),
        ),
        clock=_clock,
        event_id_factory=lambda: "event-001",
    )

    service.track_confirmed_signal(
        _signal_record(),
    )

    with pytest.raises(
        OSError,
        match="disk unavailable",
    ):
        service.register_result(
            ManualSignalResult.LOSS,
        )

    assert service.pending_count == 1
    assert service.recorded_count == 0


def test_manual_result_session_localizes_naive_signal_datetime() -> None:
    writer = FakeWriter()
    chile_timezone = timezone(
        timedelta(
            hours=-4,
        )
    )
    resolver_calls: list[datetime] = []

    def resolve_naive_datetime(
        value: datetime,
    ) -> datetime:
        resolver_calls.append(
            value,
        )

        return value.replace(
            tzinfo=chile_timezone,
        )

    naive_created_at = datetime(
        2026,
        7,
        21,
        22,
        33,
        2,
    )

    service = ManualSignalResultSessionService(
        writer=writer,
        clock=_clock,
        event_id_factory=lambda: "event-naive-001",
        naive_datetime_resolver=resolve_naive_datetime,
    )

    signal = _signal_record(
        direction=SignalDirection.PUT,
        created_at=naive_created_at,
    )

    service.track_confirmed_signal(
        signal,
    )
    persisted_record = service.register_result(
        ManualSignalResult.WIN,
    )

    assert persisted_record is not None
    assert persisted_record.signal_created_at == datetime(
        2026,
        7,
        21,
        22,
        33,
        2,
        tzinfo=chile_timezone,
    )
    assert resolver_calls == [
        naive_created_at,
    ]
    assert writer.records == [
        persisted_record,
    ]


def test_manual_result_session_preserves_aware_signal_datetime() -> None:
    writer = FakeWriter()
    aware_created_at = datetime(
        2026,
        7,
        21,
        22,
        33,
        2,
        tzinfo=timezone.utc,
    )

    def unexpected_resolver(
        value: datetime,
    ) -> datetime:
        raise AssertionError(
            "El resolver no debe usarse para fechas conscientes."
        )

    service = ManualSignalResultSessionService(
        writer=writer,
        clock=_clock,
        event_id_factory=lambda: "event-aware-001",
        naive_datetime_resolver=unexpected_resolver,
    )

    service.track_confirmed_signal(
        _signal_record(
            created_at=aware_created_at,
        ),
    )

    persisted_record = service.register_result(
        ManualSignalResult.LOSS,
    )

    assert persisted_record is not None
    assert persisted_record.signal_created_at == aware_created_at