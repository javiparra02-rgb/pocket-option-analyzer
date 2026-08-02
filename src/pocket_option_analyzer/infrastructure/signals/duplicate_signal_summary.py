from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from pocket_option_analyzer.domain.signals import (
    SignalDirection,
    SignalRecord,
    SignalRecordDisposition,
)


@dataclass(
    frozen=True,
    slots=True,
)
class DuplicateSignalSummary:
    """
    Resume las señales accionables suprimidas dentro de una vela S30.

    El resumen conserva:

    - dirección de la señal aceptada;
    - número total de repeticiones;
    - número de repeticiones CALL y PUT;
    - primera y última repetición;
    - intervalo temporal al que pertenecen.
    """

    candle_interval_started_at: datetime

    accepted_direction: SignalDirection

    accepted_record_found: bool

    source: str

    duplicate_suppressed_count: int

    call_duplicate_count: int

    put_duplicate_count: int

    first_duplicate_at: datetime

    last_duplicate_at: datetime

    def __post_init__(
        self,
    ) -> None:
        if self.accepted_direction is SignalDirection.NONE:
            raise ValueError("accepted_direction no puede ser NONE.")

        if not self.source.strip():
            raise ValueError("source no puede estar vacío.")

        if self.duplicate_suppressed_count < 1:
            raise ValueError("duplicate_suppressed_count debe ser mayor o igual a 1.")

        if self.call_duplicate_count < 0:
            raise ValueError("call_duplicate_count no puede ser negativo.")

        if self.put_duplicate_count < 0:
            raise ValueError("put_duplicate_count no puede ser negativo.")

        if (
            self.call_duplicate_count + self.put_duplicate_count
            != self.duplicate_suppressed_count
        ):
            raise ValueError(
                "Los conteos CALL y PUT deben coincidir con duplicate_suppressed_count."
            )

        if self.last_duplicate_at < self.first_duplicate_at:
            raise ValueError(
                "last_duplicate_at no puede ser anterior a first_duplicate_at."
            )

    @classmethod
    def start(
        cls,
        record: SignalRecord,
        accepted_direction: SignalDirection,
        accepted_record_found: bool,
    ) -> DuplicateSignalSummary:
        """
        Crea el resumen a partir de la primera repetición.
        """

        cls._validate_duplicate_record(
            record=record,
        )

        interval_started_at = record.candle_interval_started_at

        if interval_started_at is None:
            raise ValueError(
                "La señal duplicada debe incluir candle_interval_started_at."
            )

        return cls(
            candle_interval_started_at=interval_started_at,
            accepted_direction=accepted_direction,
            accepted_record_found=accepted_record_found,
            source=record.source,
            duplicate_suppressed_count=1,
            call_duplicate_count=int(record.signal.direction is SignalDirection.CALL),
            put_duplicate_count=int(record.signal.direction is SignalDirection.PUT),
            first_duplicate_at=record.created_at,
            last_duplicate_at=record.created_at,
        )

    def add(
        self,
        record: SignalRecord,
    ) -> DuplicateSignalSummary:
        """
        Incorpora otra repetición perteneciente a la misma vela.
        """

        self._validate_duplicate_record(
            record=record,
        )

        if record.candle_interval_started_at != self.candle_interval_started_at:
            raise ValueError("La señal duplicada pertenece a otro intervalo.")

        return replace(
            self,
            duplicate_suppressed_count=(self.duplicate_suppressed_count + 1),
            call_duplicate_count=(
                self.call_duplicate_count
                + int(record.signal.direction is SignalDirection.CALL)
            ),
            put_duplicate_count=(
                self.put_duplicate_count
                + int(record.signal.direction is SignalDirection.PUT)
            ),
            first_duplicate_at=min(
                self.first_duplicate_at,
                record.created_at,
            ),
            last_duplicate_at=max(
                self.last_duplicate_at,
                record.created_at,
            ),
        )

    @staticmethod
    def _validate_duplicate_record(
        record: SignalRecord,
    ) -> None:
        if record.disposition is not SignalRecordDisposition.DUPLICATE_SUPPRESSED:
            raise ValueError("El registro debe ser una señal duplicada suprimida.")

        if record.signal.direction is SignalDirection.NONE:
            raise ValueError("Una señal duplicada no puede tener dirección NONE.")
