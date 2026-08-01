from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from pocket_option_analyzer.domain.signals import (
    MarketSignal,
    SignalDirection,
    SignalRecord,
    SignalRecordDisposition,
    SignalStrength,
)
from pocket_option_analyzer.infrastructure.signals import (
    JsonlSignalRecordWriter,
)


def test_jsonl_signal_record_writer_creates_file_with_record(
    tmp_path,
) -> None:

    file_path = tmp_path / "signals" / "signals.jsonl"

    writer = JsonlSignalRecordWriter(
        file_path=file_path,
    )

    record = SignalRecord(
        signal=MarketSignal(
            direction=SignalDirection.PUT,
            strength=SignalStrength.HIGH,
            reason="Strategy conditions confirmed.",
        ),
        created_at=datetime(
            2026,
            1,
            1,
            tzinfo=timezone.utc,
        ),
        source="test_source",
    )

    writer.write(record)

    assert file_path.exists()

    lines = file_path.read_text(
        encoding="utf-8",
    ).splitlines()

    assert len(lines) == 1

    data = json.loads(lines[0])

    assert data["created_at"] == "2026-01-01T00:00:00+00:00"
    assert data["source"] == "test_source"
    assert data["direction"] == "put"
    assert data["strength"] == "high"
    assert data["reason"] == "Strategy conditions confirmed."
    assert data["is_actionable"] is True


def _record(
    disposition: SignalRecordDisposition,
    created_second: int,
    interval_second: int,
    direction: SignalDirection = SignalDirection.NONE,
    reason: str = "Test analysis.",
) -> SignalRecord:

    strength = (
        SignalStrength.NONE
        if direction is SignalDirection.NONE
        else SignalStrength.HIGH
    )

    return SignalRecord(
        signal=MarketSignal(
            direction=direction,
            strength=strength,
            reason=reason,
        ),
        created_at=datetime(
            2026,
            8,
            1,
            20,
            51,
            created_second,
            tzinfo=timezone.utc,
        ),
        source="writer_test",
        disposition=disposition,
        candle_interval_started_at=datetime(
            2026,
            8,
            1,
            20,
            51,
            interval_second,
            tzinfo=timezone.utc,
        ),
    )


def _read_jsonl(
    file_path: Path,
) -> list[dict]:

    return [
        json.loads(
            line,
        )
        for line in file_path.read_text(
            encoding="utf-8",
        ).splitlines()
        if line.strip()
    ]


def test_writer_persists_only_first_observed_record_per_interval(
    tmp_path: Path,
) -> None:

    file_path = (
        tmp_path
        / "signals.jsonl"
    )

    writer = JsonlSignalRecordWriter(
        file_path=file_path,
    )

    writer.write(
        _record(
            disposition=SignalRecordDisposition.OBSERVED,
            created_second=2,
            interval_second=0,
        )
    )

    writer.write(
        _record(
            disposition=SignalRecordDisposition.OBSERVED,
            created_second=10,
            interval_second=0,
        )
    )

    writer.write(
        _record(
            disposition=SignalRecordDisposition.OBSERVED,
            created_second=20,
            interval_second=0,
        )
    )

    writer.write(
        _record(
            disposition=SignalRecordDisposition.OBSERVED,
            created_second=35,
            interval_second=30,
        )
    )

    records = _read_jsonl(
        file_path=file_path,
    )

    assert len(records) == 2

    assert records[0][
        "candle_interval_started_at"
    ] == "2026-08-01T20:51:00+00:00"

    assert records[1][
        "candle_interval_started_at"
    ] == "2026-08-01T20:51:30+00:00"

    assert all(
        record["storage_format"] == "full"
        for record in records
    )


def test_writer_updates_single_duplicate_summary_in_place(
    tmp_path: Path,
) -> None:

    file_path = (
        tmp_path
        / "signals.jsonl"
    )

    writer = JsonlSignalRecordWriter(
        file_path=file_path,
    )

    writer.write(
        _record(
            disposition=(
                SignalRecordDisposition.ACTIONABLE_ACCEPTED
            ),
            created_second=32,
            interval_second=30,
            direction=SignalDirection.CALL,
            reason="Accepted diagnostics.",
        )
    )

    for created_second in (
        33,
        34,
        35,
    ):
        writer.write(
            _record(
                disposition=(
                    SignalRecordDisposition.DUPLICATE_SUPPRESSED
                ),
                created_second=created_second,
                interval_second=30,
                direction=SignalDirection.CALL,
                reason="Repeated diagnostics.",
            )
        )

    records = _read_jsonl(
        file_path=file_path,
    )

    assert len(records) == 2

    accepted = records[0]
    summary = records[1]

    assert accepted["storage_format"] == "full"
    assert accepted["reason"] == (
        "Accepted diagnostics."
    )

    assert summary["storage_format"] == "summary"
    assert summary["event_type"] == (
        "duplicate_signal_summary"
    )
    assert summary["accepted_direction"] == "call"

    assert (
        summary["duplicate_suppressed_count"]
        == 3
    )

    assert summary["duplicate_direction_counts"] == {
        "call": 3,
        "put": 0,
    }

    assert "reason" not in summary

    assert summary["is_actionable"] is False

    assert (
        summary["is_duplicate_suppressed"]
        is True
    )


def test_writer_rotates_files_and_respects_backup_limit(
    tmp_path: Path,
) -> None:

    file_path = (
        tmp_path
        / "signals.jsonl"
    )

    writer = JsonlSignalRecordWriter(
        file_path=file_path,
        max_bytes=400,
        backup_count=2,
    )

    large_reason = "X" * 1000

    writer.write(
        _record(
            disposition=(
                SignalRecordDisposition.ACTIONABLE_ACCEPTED
            ),
            created_second=5,
            interval_second=0,
            direction=SignalDirection.CALL,
            reason=large_reason,
        )
    )

    writer.write(
        _record(
            disposition=(
                SignalRecordDisposition.ACTIONABLE_ACCEPTED
            ),
            created_second=10,
            interval_second=0,
            direction=SignalDirection.PUT,
            reason=large_reason,
        )
    )

    writer.write(
        _record(
            disposition=(
                SignalRecordDisposition.ACTIONABLE_ACCEPTED
            ),
            created_second=35,
            interval_second=30,
            direction=SignalDirection.CALL,
            reason=large_reason,
        )
    )

    assert file_path.exists() is True

    assert Path(
        f"{file_path}.1"
    ).exists() is True

    assert Path(
        f"{file_path}.2"
    ).exists() is True

    assert Path(
        f"{file_path}.3"
    ).exists() is False


def test_writer_rejects_invalid_rotation_configuration(
    tmp_path: Path,
) -> None:

    with pytest.raises(
        ValueError,
        match="max_bytes debe ser mayor o igual a 1",
    ):
        JsonlSignalRecordWriter(
            file_path=(
                tmp_path
                / "signals.jsonl"
            ),
            max_bytes=0,
        )

    with pytest.raises(
        ValueError,
        match="backup_count no puede ser negativo",
    ):
        JsonlSignalRecordWriter(
            file_path=(
                tmp_path
                / "signals.jsonl"
            ),
            backup_count=-1,
        )


def test_writer_creates_independent_summary_for_next_interval(
    tmp_path: Path,
) -> None:

    file_path = (
        tmp_path
        / "signals.jsonl"
    )

    writer = JsonlSignalRecordWriter(
        file_path=file_path,
    )

    writer.write(
        _record(
            disposition=(
                SignalRecordDisposition.ACTIONABLE_ACCEPTED
            ),
            created_second=5,
            interval_second=0,
            direction=SignalDirection.CALL,
        )
    )

    writer.write(
        _record(
            disposition=(
                SignalRecordDisposition.DUPLICATE_SUPPRESSED
            ),
            created_second=10,
            interval_second=0,
            direction=SignalDirection.CALL,
        )
    )

    writer.write(
        _record(
            disposition=(
                SignalRecordDisposition.ACTIONABLE_ACCEPTED
            ),
            created_second=35,
            interval_second=30,
            direction=SignalDirection.PUT,
        )
    )

    writer.write(
        _record(
            disposition=(
                SignalRecordDisposition.DUPLICATE_SUPPRESSED
            ),
            created_second=40,
            interval_second=30,
            direction=SignalDirection.PUT,
        )
    )

    records = _read_jsonl(
        file_path=file_path,
    )

    summaries = [
        record
        for record in records
        if record.get(
            "event_type",
        ) == "duplicate_signal_summary"
    ]

    assert len(summaries) == 2

    assert summaries[0][
        "accepted_direction"
    ] == "call"

    assert summaries[1][
        "accepted_direction"
    ] == "put"


def test_writer_skips_observed_after_accepted_signal(
    tmp_path: Path,
) -> None:

    file_path = (
        tmp_path
        / "signals.jsonl"
    )

    writer = JsonlSignalRecordWriter(
        file_path=file_path,
    )

    writer.write(
        _record(
            disposition=(
                SignalRecordDisposition.ACTIONABLE_ACCEPTED
            ),
            created_second=5,
            interval_second=0,
            direction=SignalDirection.CALL,
        )
    )

    writer.write(
        _record(
            disposition=SignalRecordDisposition.OBSERVED,
            created_second=20,
            interval_second=0,
            direction=SignalDirection.NONE,
        )
    )

    records = _read_jsonl(
        file_path=file_path,
    )

    assert len(records) == 1

    assert records[0]["disposition"] == (
        "actionable_accepted"
    )