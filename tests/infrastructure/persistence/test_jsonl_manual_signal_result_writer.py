from __future__ import annotations

import json
from datetime import datetime, timezone

from pocket_option_analyzer.domain.session_results import (
    ManualSignalResult,
    ManualSignalResultRecord,
)
from pocket_option_analyzer.domain.signals import (
    SignalDirection,
    SignalStrength,
)
from pocket_option_analyzer.infrastructure.persistence import (
    JsonlManualSignalResultWriter,
)


def _record(
    result: ManualSignalResult,
    reason: str = "Señal confirmada.",
) -> ManualSignalResultRecord:
    return ManualSignalResultRecord(
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
        result=result,
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
        reason=reason,
    )


def test_jsonl_writer_creates_parent_directory_and_file(
    tmp_path,
) -> None:
    output_path = (
        tmp_path
        / "logs"
        / "manual_results.jsonl"
    )
    writer = JsonlManualSignalResultWriter(
        output_path=output_path,
    )

    writer.append(
        record=_record(
            result=ManualSignalResult.WIN,
        ),
    )

    assert output_path.exists() is True
    assert writer.output_path == output_path


def test_jsonl_writer_appends_without_overwriting_existing_records(
    tmp_path,
) -> None:
    output_path = tmp_path / "manual_results.jsonl"
    writer = JsonlManualSignalResultWriter(
        output_path=output_path,
    )

    writer.append(
        record=_record(
            result=ManualSignalResult.WIN,
        ),
    )
    writer.append(
        record=_record(
            result=ManualSignalResult.LOSS,
        ),
    )

    lines = output_path.read_text(
        encoding="utf-8",
    ).splitlines()

    assert len(lines) == 2
    assert json.loads(
        lines[0],
    )["result"] == "WIN"
    assert json.loads(
        lines[1],
    )["result"] == "LOSS"


def test_jsonl_writer_writes_valid_utf8_json(
    tmp_path,
) -> None:
    output_path = tmp_path / "manual_results.jsonl"
    writer = JsonlManualSignalResultWriter(
        output_path=output_path,
    )

    writer.append(
        record=_record(
            result=ManualSignalResult.LOSS,
            reason="Señal bajista confirmada.",
        ),
    )

    stored_payload = json.loads(
        output_path.read_text(
            encoding="utf-8",
        ).strip()
    )

    assert stored_payload["reason"] == "Señal bajista confirmada."
    assert stored_payload["direction"] == SignalDirection.PUT.value
    assert stored_payload["result"] == "LOSS"