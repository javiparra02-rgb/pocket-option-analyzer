from __future__ import annotations

from typing import Protocol

from pocket_option_analyzer.domain.signals import SignalRecord


class SignalRecordWriter(Protocol):
    """
    Contrato para persistir registros de señales.

    La capa application solo conoce este contrato.
    La implementación concreta vive en infrastructure.
    """

    def write(
        self,
        record: SignalRecord,
    ) -> None:
        """
        Persiste un registro de señal.
        """