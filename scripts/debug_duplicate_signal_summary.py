from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

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

OUTPUT_DIRECTORY = Path("debug") / "duplicate_signal_summary"

OUTPUT_FILE = OUTPUT_DIRECTORY / "signals.jsonl"


def _record(
    disposition: SignalRecordDisposition,
    second: int,
    direction: SignalDirection,
) -> SignalRecord:

    return SignalRecord(
        signal=MarketSignal(
            direction=direction,
            strength=(
                SignalStrength.NONE
                if direction is SignalDirection.NONE
                else SignalStrength.HIGH
            ),
            reason=("Deterministic duplicate summary test."),
        ),
        created_at=datetime(
            2026,
            8,
            1,
            20,
            51,
            second,
            tzinfo=UTC,
        ),
        source="debug_duplicate_signal_summary",
        disposition=disposition,
        candle_interval_started_at=datetime(
            2026,
            8,
            1,
            20,
            51,
            30,
            tzinfo=UTC,
        ),
    )


def main() -> None:

    shutil.rmtree(
        OUTPUT_DIRECTORY,
        ignore_errors=True,
    )

    writer = JsonlSignalRecordWriter(
        file_path=OUTPUT_FILE,
    )

    writer.write(
        _record(
            disposition=(SignalRecordDisposition.ACTIONABLE_ACCEPTED),
            second=32,
            direction=SignalDirection.CALL,
        )
    )

    for second in range(
        33,
        59,
    ):
        writer.write(
            _record(
                disposition=(SignalRecordDisposition.DUPLICATE_SUPPRESSED),
                second=second,
                direction=SignalDirection.CALL,
            )
        )

    records = [
        json.loads(
            line,
        )
        for line in OUTPUT_FILE.read_text(
            encoding="utf-8",
        ).splitlines()
        if line.strip()
    ]

    print(f"Registros físicos: {len(records)}")

    for record in records:
        print(
            json.dumps(
                record,
                ensure_ascii=False,
                indent=2,
            )
        )

    summary = next(
        record
        for record in records
        if record.get(
            "event_type",
        )
        == "duplicate_signal_summary"
    )

    print(f"Duplicadas resumidas: {summary['duplicate_suppressed_count']}")

    print(f"Tamaño: {OUTPUT_FILE.stat().st_size} bytes")


if __name__ == "__main__":
    main()
