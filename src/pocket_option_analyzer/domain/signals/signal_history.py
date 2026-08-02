from __future__ import annotations

from dataclasses import dataclass, field

from .signal_record import SignalRecord


@dataclass(slots=True)
class SignalHistory:
    """
    Historial en memoria de señales generadas.

    Esta clase no escribe archivos.
    Solo mantiene los registros durante la ejecución.
    """

    records: list[SignalRecord] = field(default_factory=list)

    def append(
        self,
        record: SignalRecord,
    ) -> None:
        """
        Agrega un registro al historial.
        """

        self.records.append(record)

    def clear(self) -> None:
        """
        Limpia el historial.
        """

        self.records.clear()

    def latest(self) -> SignalRecord | None:
        """
        Devuelve la señal más reciente registrada.
        """

        if not self.records:
            return None

        return self.records[-1]

    def actionable(self) -> list[SignalRecord]:
        """
        Devuelve solo los registros con señales CALL o PUT.
        """

        return [record for record in self.records if record.is_actionable]
