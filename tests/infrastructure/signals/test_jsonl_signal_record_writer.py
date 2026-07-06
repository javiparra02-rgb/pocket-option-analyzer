from __future__ import annotations

import json
from datetime import datetime, timezone

from pocket_option_analyzer.domain.signals import (
    MarketSignal,
    SignalDirection,
    SignalRecord,
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