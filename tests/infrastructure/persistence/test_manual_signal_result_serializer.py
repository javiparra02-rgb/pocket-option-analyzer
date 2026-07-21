from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pocket_option_analyzer.domain.session_results import (
    ManualSignalResult,
    ManualSignalResultRecord,
)
from pocket_option_analyzer.domain.signals import (
    SignalDirection,
    SignalStrength,
)
from pocket_option_analyzer.infrastructure.persistence import (
    ManualSignalResultSerializer,
)


def _record(
    signal_created_at: datetime | None = None,
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
        direction=SignalDirection.CALL,
        strength=SignalStrength.HIGH,
        result=ManualSignalResult.WIN,
        registered_at=datetime(
            2026,
            7,
            20,
            16,
            3,
            47,
            tzinfo=timezone.utc,
        ),
        source="captured_frame_visual_analysis",
        reason="CALL strategy conditions confirmed.",
    )


def test_manual_signal_result_serializer_builds_expected_payload() -> None:
    serializer = ManualSignalResultSerializer()

    payload = serializer.serialize(
        record=_record(),
    )

    assert payload == {
        "schema_version": 1,
        "strategy": "OTC_PRECISION_10S",
        "signal_created_at": "2026-07-20T16:03:25Z",
        "direction": SignalDirection.CALL.value,
        "strength": SignalStrength.HIGH.value,
        "result": "WIN",
        "registered_at": "2026-07-20T16:03:47Z",
        "source": "captured_frame_visual_analysis",
        "reason": "CALL strategy conditions confirmed.",
    }


def test_manual_signal_result_serializer_normalizes_datetime_to_utc() -> None:
    serializer = ManualSignalResultSerializer()
    chile_offset = timezone(
        timedelta(
            hours=-4,
        )
    )

    record = _record(
        signal_created_at=datetime(
            2026,
            7,
            20,
            12,
            3,
            25,
            tzinfo=chile_offset,
        ),
    )

    payload = serializer.serialize(
        record=record,
    )

    assert payload["signal_created_at"] == "2026-07-20T16:03:25Z"


def test_manual_signal_result_serializer_preserves_unicode() -> None:
    serializer = ManualSignalResultSerializer()

    record = ManualSignalResultRecord(
        signal_created_at=datetime(
            2026,
            7,
            20,
            16,
            3,
            25,
            tzinfo=timezone.utc,
        ),
        direction=SignalDirection.PUT,
        strength=SignalStrength.HIGH,
        result=ManualSignalResult.LOSS,
        registered_at=datetime(
            2026,
            7,
            20,
            16,
            3,
            47,
            tzinfo=timezone.utc,
        ),
        source="análisis_visual",
        reason="Señal bajista confirmada.",
    )

    payload = serializer.serialize(
        record=record,
    )

    assert payload["source"] == "análisis_visual"
    assert payload["reason"] == "Señal bajista confirmada."