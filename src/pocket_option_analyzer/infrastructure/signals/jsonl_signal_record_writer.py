from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pocket_option_analyzer.domain.signals import (
    SignalDirection,
    SignalRecord,
    SignalRecordDisposition,
)
from pocket_option_analyzer.infrastructure.signals.duplicate_signal_summary import (
    DuplicateSignalSummary,
)
from pocket_option_analyzer.infrastructure.signals.signal_record_serializer import (
    SignalRecordSerializer,
)


class JsonlSignalRecordWriter:
    """
    Persiste señales aplicando muestreo, resúmenes y rotación.

    Política:

    OBSERVED:
        Solo se guarda la primera observación de cada vela S30.

    ACTIONABLE_ACCEPTED:
        Se guarda siempre con diagnóstico completo.

    DUPLICATE_SUPPRESSED:
        Se acumula en una sola línea de resumen por vela.

    La línea del resumen permanece al final del archivo durante la
    vela y se actualiza mediante seek + truncate + write.
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

        self._last_accepted_interval_started_at: (
            datetime
            | None
        ) = None

        self._last_accepted_direction: (
            SignalDirection
            | None
        ) = None

        self._active_duplicate_summary: (
            DuplicateSignalSummary
            | None
        ) = None

        self._active_duplicate_summary_offset: (
            int
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

    @property
    def active_duplicate_summary(
        self,
    ) -> DuplicateSignalSummary | None:
        return self._active_duplicate_summary

    def write(
        self,
        record: SignalRecord,
    ) -> None:
        """
        Persiste o acumula el registro recibido.
        """

        self._release_summary_if_interval_changed(
            record=record,
        )

        if (
            record.disposition
            is SignalRecordDisposition.DUPLICATE_SUPPRESSED
        ):
            self._write_duplicate_summary(
                record=record,
            )
            return

        if self._should_skip_observed(
            record=record,
        ):
            return

        data = self._serializer.to_dict(
            record=record,
        )

        self._append_data(
            data=data,
        )

        self._remember_record(
            record=record,
        )

    def _should_skip_observed(
        self,
        record: SignalRecord,
    ) -> bool:
        """
        Omite observaciones repetidas o posteriores a una señal
        ya persistida dentro de la misma vela.
        """

        if (
            record.disposition
            is not SignalRecordDisposition.OBSERVED
        ):
            return False

        interval_started_at = (
            record.candle_interval_started_at
        )

        if interval_started_at is None:
            return False

        if (
            interval_started_at
            == self._last_observed_interval_started_at
        ):
            return True

        if (
            interval_started_at
            == self._last_accepted_interval_started_at
        ):
            return True

        active_summary = (
            self._active_duplicate_summary
        )

        return (
            active_summary is not None
            and interval_started_at
            == active_summary.candle_interval_started_at
        )

    def _remember_record(
        self,
        record: SignalRecord,
    ) -> None:
        interval_started_at = (
            record.candle_interval_started_at
        )

        if interval_started_at is None:
            return

        if (
            record.disposition
            is SignalRecordDisposition.OBSERVED
        ):
            self._last_observed_interval_started_at = (
                interval_started_at
            )
            return

        if (
            record.disposition
            is SignalRecordDisposition.ACTIONABLE_ACCEPTED
        ):
            self._last_accepted_interval_started_at = (
                interval_started_at
            )

            self._last_accepted_direction = (
                record.signal.direction
            )

    def _write_duplicate_summary(
        self,
        record: SignalRecord,
    ) -> None:
        interval_started_at = (
            record.candle_interval_started_at
        )

        if interval_started_at is None:
            raise ValueError(
                "La señal duplicada debe incluir "
                "candle_interval_started_at."
            )

        active_summary = (
            self._active_duplicate_summary
        )

        if (
            active_summary is not None
            and active_summary.candle_interval_started_at
            == interval_started_at
        ):
            updated_summary = active_summary.add(
                record=record,
            )

            self._replace_active_summary(
                summary=updated_summary,
            )
            return

        accepted_record_found = (
            self._last_accepted_interval_started_at
            == interval_started_at
            and self._last_accepted_direction is not None
        )

        accepted_direction = (
            self._last_accepted_direction
            if accepted_record_found
            else record.signal.direction
        )

        if accepted_direction is None:
            accepted_direction = (
                record.signal.direction
            )

        summary = DuplicateSignalSummary.start(
            record=record,
            accepted_direction=accepted_direction,
            accepted_record_found=accepted_record_found,
        )

        offset = self._append_data(
            data=(
                self._serializer.to_duplicate_summary_dict(
                    summary=summary,
                )
            ),
        )

        self._active_duplicate_summary = summary
        self._active_duplicate_summary_offset = offset

    def _replace_active_summary(
        self,
        summary: DuplicateSignalSummary,
    ) -> None:
        """
        Reemplaza la última línea del archivo por el resumen actualizado.
        """

        offset = (
            self._active_duplicate_summary_offset
        )

        if (
            offset is None
            or not self._file_path.exists()
            or self._file_path.stat().st_size < offset
        ):
            new_offset = self._append_data(
                data=(
                    self._serializer.to_duplicate_summary_dict(
                        summary=summary,
                    )
                ),
            )

            self._active_duplicate_summary = summary
            self._active_duplicate_summary_offset = (
                new_offset
            )
            return

        encoded_line = self._encode_data(
            data=(
                self._serializer.to_duplicate_summary_dict(
                    summary=summary,
                )
            ),
        )

        with self._file_path.open(
            mode="r+b",
        ) as file:
            file.seek(
                offset,
            )
            file.truncate()
            file.write(
                encoded_line,
            )

        self._active_duplicate_summary = summary

    def _release_summary_if_interval_changed(
        self,
        record: SignalRecord,
    ) -> None:
        """
        Libera la referencia editable cuando comienza otra vela.

        El resumen anterior ya permanece finalizado en disco.
        """

        active_summary = (
            self._active_duplicate_summary
        )

        if active_summary is None:
            return

        if (
            record.candle_interval_started_at
            == active_summary.candle_interval_started_at
        ):
            return

        self._active_duplicate_summary = None
        self._active_duplicate_summary_offset = None

    def _append_data(
        self,
        data: dict[str, Any],
    ) -> int:
        """
        Agrega una línea y devuelve su desplazamiento inicial en bytes.
        """

        encoded_line = self._encode_data(
            data=data,
        )

        self._file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._rotate_if_required(
            incoming_size=len(
                encoded_line,
            ),
        )

        offset = (
            self._file_path.stat().st_size
            if self._file_path.exists()
            else 0
        )

        with self._file_path.open(
            mode="ab",
        ) as file:
            file.write(
                encoded_line,
            )

        return offset

    @staticmethod
    def _encode_data(
        data: dict[str, Any],
    ) -> bytes:
        serialized_line = json.dumps(
            data,
            ensure_ascii=False,
            separators=(
                ",",
                ":",
            ),
        )

        return (
            serialized_line
            + "\n"
        ).encode(
            "utf-8",
        )

    def _rotate_if_required(
        self,
        incoming_size: int,
    ) -> None:
        if not self._file_path.exists():
            return

        current_size = (
            self._file_path.stat().st_size
        )

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

            source.replace(
                self._backup_path(
                    index=index + 1,
                )
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