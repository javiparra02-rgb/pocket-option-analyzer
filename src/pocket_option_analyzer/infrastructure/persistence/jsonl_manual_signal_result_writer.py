from __future__ import annotations

import json
from pathlib import Path

from pocket_option_analyzer.domain.session_results import (
    ManualSignalResultRecord,
)
from pocket_option_analyzer.infrastructure.persistence.manual_signal_result_serializer import (
    ManualSignalResultSerializer,
)


class JsonlManualSignalResultWriter:
    """
    Persiste resultados manuales en formato JSON Lines.

    Cada línea contiene un registro independiente. Los nuevos registros
    se agregan al final y nunca sobrescriben los anteriores.
    """

    def __init__(
        self,
        output_path: str | Path,
        serializer: ManualSignalResultSerializer | None = None,
    ) -> None:
        self._output_path = Path(
            output_path,
        )
        self._serializer = (
            serializer
            or ManualSignalResultSerializer()
        )

    @property
    def output_path(self) -> Path:
        return self._output_path

    def append(
        self,
        record: ManualSignalResultRecord,
    ) -> None:
        payload = self._serializer.serialize(
            record=record,
        )

        self._output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        serialized_record = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(
                ",",
                ":",
            ),
        )

        with self._output_path.open(
            mode="a",
            encoding="utf-8",
            newline="\n",
        ) as output_file:
            output_file.write(
                serialized_record,
            )
            output_file.write(
                "\n",
            )