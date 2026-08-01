from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pocket_option_analyzer.domain.signals import (
    SignalRecord,
    SignalRecordDisposition,
)
from pocket_option_analyzer.infrastructure.signals.signal_record_serializer import (
    SignalRecordSerializer,
)


class JsonlSignalRecordWriter:
    """
    Persiste señales en JSONL aplicando control de crecimiento.

    Política:

    OBSERVED:
        Se guarda únicamente la primera observación completa
        de cada intervalo de vela.

    ACTIONABLE_ACCEPTED:
        Siempre se guarda en formato completo.

    DUPLICATE_SUPPRESSED:
        Siempre se guarda, pero en formato compacto.

    El archivo rota automáticamente cuando supera max_bytes.
    """

    DEFAULT_MAX_BYTES = 5 * 1024 * 1024

    DEFAULT_BACKUP_COUNT = 5

    def __init__(
        self,
        file_path: Path,
        serializer: SignalRecordSerializer | None = None,
        max_bytes: int = DEFAULT_MAX_BYTES,
        backup_count: int = DEFAULT_BACKUP_COUNT,
    ) -> None:
        if max_bytes < 1:
            raise ValueError(
                "max_bytes debe ser mayor o igual a 1."
            )

        if backup_count < 0:
            raise ValueError(
                "backup_count no puede ser negativo."
            )

        self._file_path = file_path
        self._serializer = (
            serializer
            or SignalRecordSerializer()
        )
        self._max_bytes = max_bytes
        self._backup_count = backup_count

        self._last_observed_interval_started_at: (
            datetime
            | None
        ) = None

    @property
    def file_path(
        self,
    ) -> Path:
        return self._file_path

    @property
    def max_bytes(
        self,
    ) -> int:
        return self._max_bytes

    @property
    def backup_count(
        self,
    ) -> int:
        return self._backup_count

    def write(
        self,
        record: SignalRecord,
    ) -> None:
        """
        Persiste el registro cuando cumple la política configurada.
        """

        if self._should_skip(
            record=record,
        ):
            return

        data = self._serialize_record(
            record=record,
        )

        serialized_line = json.dumps(
            data,
            ensure_ascii=False,
            separators=(
                ",",
                ":",
            ),
        )

        encoded_size = len(
            (
                serialized_line
                + "\n"
            ).encode(
                "utf-8",
            )
        )

        self._file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._rotate_if_required(
            incoming_size=encoded_size,
        )

        with self._file_path.open(
            mode="a",
            encoding="utf-8",
            newline="\n",
        ) as file:
            file.write(
                serialized_line,
            )
            file.write(
                "\n",
            )

        self._remember_persisted_record(
            record=record,
        )

    def _should_skip(
        self,
        record: SignalRecord,
    ) -> bool:
        """
        Omite observaciones repetidas dentro de una misma vela.

        Señales aceptadas y duplicadas nunca se omiten.
        """

        if (
            record.disposition
            is not SignalRecordDisposition.OBSERVED
        ):
            return False

        interval_started_at = (
            record.candle_interval_started_at
        )

        # Registros antiguos o externos sin clave temporal se
        # conservan para mantener compatibilidad.
        if interval_started_at is None:
            return False

        return (
            interval_started_at
            == self._last_observed_interval_started_at
        )

    def _serialize_record(
        self,
        record: SignalRecord,
    ) -> dict[str, Any]:
        """
        Selecciona la representación completa o compacta.
        """

        if (
            record.disposition
            is SignalRecordDisposition.DUPLICATE_SUPPRESSED
        ):
            return self._serializer.to_compact_dict(
                record=record,
            )

        return self._serializer.to_dict(
            record=record,
        )

    def _remember_persisted_record(
        self,
        record: SignalRecord,
    ) -> None:
        """
        Recuerda el intervalo de la última observación persistida.
        """

        if (
            record.disposition
            is not SignalRecordDisposition.OBSERVED
        ):
            return

        if record.candle_interval_started_at is None:
            return

        self._last_observed_interval_started_at = (
            record.candle_interval_started_at
        )

    def _rotate_if_required(
        self,
        incoming_size: int,
    ) -> None:
        """
        Rota el archivo antes de superar el límite configurado.

        Un único registro mayor que max_bytes se conserva completo
        cuando el archivo actual está vacío.
        """

        if not self._file_path.exists():
            return

        current_size = self._file_path.stat().st_size

        if current_size == 0:
            return

        if (
            current_size
            + incoming_size
            <= self._max_bytes
        ):
            return

        self._rotate_files()

    def _rotate_files(
        self,
    ) -> None:
        """
        Desplaza los archivos existentes:

        signals.jsonl.4 -> signals.jsonl.5
        signals.jsonl.3 -> signals.jsonl.4
        ...
        signals.jsonl   -> signals.jsonl.1
        """

        if self._backup_count == 0:
            self._file_path.unlink(
                missing_ok=True,
            )
            return

        oldest_backup = self._backup_path(
            index=self._backup_count,
        )

        oldest_backup.unlink(
            missing_ok=True,
        )

        for index in range(
            self._backup_count - 1,
            0,
            -1,
        ):
            source = self._backup_path(
                index=index,
            )

            if not source.exists():
                continue

            destination = self._backup_path(
                index=index + 1,
            )

            source.replace(
                destination,
            )

        if self._file_path.exists():
            self._file_path.replace(
                self._backup_path(
                    index=1,
                )
            )

    def _backup_path(
        self,
        index: int,
    ) -> Path:
        return Path(
            f"{self._file_path}.{index}"
        )