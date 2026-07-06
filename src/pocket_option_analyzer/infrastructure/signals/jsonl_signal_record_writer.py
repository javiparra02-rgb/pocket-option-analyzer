from __future__ import annotations

import json
from pathlib import Path

from pocket_option_analyzer.domain.signals import SignalRecord
from pocket_option_analyzer.infrastructure.signals.signal_record_serializer import (
    SignalRecordSerializer,
)


class JsonlSignalRecordWriter:
    """
    Escribe registros de señales en un archivo JSONL.

    No ejecuta operaciones.
    No interactúa con Pocket Option.
    Solo persiste señales informativas en disco.
    """

    def __init__(
        self,
        file_path: Path,
        serializer: SignalRecordSerializer | None = None,
    ) -> None:
        self._file_path = file_path
        self._serializer = serializer or SignalRecordSerializer()

    @property
    def file_path(self) -> Path:
        return self._file_path

    def write(
        self,
        record: SignalRecord,
    ) -> None:
        """
        Agrega un registro al archivo JSONL.
        """

        self._file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        data = self._serializer.to_dict(record)

        with self._file_path.open(
            mode="a",
            encoding="utf-8",
        ) as file:
            json.dump(
                data,
                file,
                ensure_ascii=False,
            )
            file.write("\n")