from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pocket_option_analyzer.domain.session_results import (
    ManualSignalResult,
    ManualSignalResultEventType,
    ManualSignalResultRecord,
)
from pocket_option_analyzer.domain.signals import (
    SignalDirection,
    SignalStrength,
)


def _record(
    signal_created_at: datetime | None = None,
    registered_at: datetime | None = None,
    source: str = "test_source",
) -> ManualSignalResultRecord:
    return ManualSignalResultRecord(
        signal_created_at=(
            signal_created_at
            or datetime(
                2026,
                7,
                20,
                16,
                3,
                25,
                tzinfo=UTC,
            )
        ),
        direction=SignalDirection.PUT,
        strength=SignalStrength.HIGH,
        result=ManualSignalResult.LOSS,
        registered_at=(
            registered_at
            or datetime(
                2026,
                7,
                20,
                16,
                3,
                47,
                tzinfo=UTC,
            )
        ),
        source=source,
        reason="PUT setup confirmed.",
    )


def test_manual_signal_result_record_accepts_valid_data() -> None:
    record = _record()

    assert record.direction == SignalDirection.PUT
    assert record.strength == SignalStrength.HIGH
    assert record.result == ManualSignalResult.LOSS
    assert record.strategy_name == "OTC_PRECISION_10S"


def test_manual_signal_result_record_rejects_naive_signal_datetime() -> None:
    with pytest.raises(
        ValueError,
        match="signal_created_at debe incluir zona horaria",
    ):
        _record(
            signal_created_at=datetime(
                2026,
                7,
                20,
                16,
                3,
                25,
            ),
        )


def test_manual_signal_result_record_rejects_naive_registration_datetime() -> None:
    with pytest.raises(
        ValueError,
        match="registered_at debe incluir zona horaria",
    ):
        _record(
            registered_at=datetime(
                2026,
                7,
                20,
                16,
                3,
                47,
            ),
        )


def test_manual_signal_result_record_rejects_blank_source() -> None:
    with pytest.raises(
        ValueError,
        match="source no puede estar vacío",
    ):
        _record(
            source="   ",
        )


def test_manual_signal_result_record_defaults_to_recorded_event() -> None:
    record = _record()

    assert record.event_id
    assert record.event_type == ManualSignalResultEventType.RECORDED
    assert record.reverses_event_id is None


def test_manual_signal_result_reversal_requires_original_event_id() -> None:
    with pytest.raises(
        ValueError,
        match="REVERSED debe indicar reverses_event_id",
    ):
        ManualSignalResultRecord(
            signal_created_at=datetime(
                2026,
                7,
                20,
                16,
                3,
                25,
                tzinfo=UTC,
            ),
            direction=SignalDirection.PUT,
            strength=SignalStrength.HIGH,
            result=ManualSignalResult.LOSS,
            registered_at=datetime(
                2026,
                7,
                20,
                16,
                4,
                0,
                tzinfo=UTC,
            ),
            source="test_source",
            event_type=ManualSignalResultEventType.REVERSED,
        )


def test_recorded_event_rejects_reversal_reference() -> None:
    with pytest.raises(
        ValueError,
        match="RECORDED no puede indicar reverses_event_id",
    ):
        ManualSignalResultRecord(
            signal_created_at=datetime(
                2026,
                7,
                20,
                16,
                3,
                25,
                tzinfo=UTC,
            ),
            direction=SignalDirection.CALL,
            strength=SignalStrength.HIGH,
            result=ManualSignalResult.WIN,
            registered_at=datetime(
                2026,
                7,
                20,
                16,
                4,
                0,
                tzinfo=UTC,
            ),
            source="test_source",
            event_id="event-1",
            event_type=ManualSignalResultEventType.RECORDED,
            reverses_event_id="event-original",
        )
