from __future__ import annotations

from datetime import datetime, timezone

import pytest

from pocket_option_analyzer.domain.session_results import (
    ManualSignalResult,
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
                tzinfo=timezone.utc,
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
                tzinfo=timezone.utc,
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