from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from .signal_record import SignalRecord


@dataclass(slots=True)
class SignalHistory:
    """
    Historial limitado de señales generadas durante la ejecución.

    Esta clase no escribe archivos. Mantiene únicamente los registros
    más recientes hasta alcanzar max_records.

    Cuando se supera la capacidad, elimina primero los registros
    más antiguos.
    """

    DEFAULT_MAX_RECORDS: ClassVar[int] = 10_000

    records: list[SignalRecord] = field(
        default_factory=list,
    )

    max_records: int = DEFAULT_MAX_RECORDS

    def __post_init__(
        self,
    ) -> None:
        if self.max_records < 1:
            raise ValueError("max_records debe ser mayor o igual a 1.")

        self._trim_to_capacity()

    def __len__(
        self,
    ) -> int:
        return len(
            self.records,
        )

    @property
    def is_full(
        self,
    ) -> bool:
        """
        Indica si el historial alcanzó su capacidad máxima.
        """

        return (
            len(
                self.records,
            )
            >= self.max_records
        )

    def append(
        self,
        record: SignalRecord,
    ) -> None:
        """
        Agrega un registro y elimina los más antiguos si se supera
        la capacidad configurada.
        """

        self.records.append(
            record,
        )

        self._trim_to_capacity()

    def clear(
        self,
    ) -> None:
        """
        Limpia los registros sin modificar max_records.
        """

        self.records.clear()

    def latest(
        self,
    ) -> SignalRecord | None:
        """
        Devuelve la señal más reciente registrada.
        """

        if not self.records:
            return None

        return self.records[-1]

    def actionable(
        self,
    ) -> list[SignalRecord]:
        """
        Devuelve las señales accionables actualmente retenidas.
        """

        return [record for record in self.records if record.is_actionable]

    def _trim_to_capacity(
        self,
    ) -> None:
        """
        Elimina en una sola operación los registros que excedan
        la capacidad máxima.
        """

        overflow = len(self.records) - self.max_records

        if overflow <= 0:
            return

        del self.records[:overflow]
