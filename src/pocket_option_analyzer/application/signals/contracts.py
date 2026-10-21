from __future__ import annotations

from typing import Protocol

from pocket_option_analyzer.domain.signals import SignalRecord

from .accepted_signal_evidence import AcceptedSignalEvidence


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


class AcceptedSignalRecordWriter(SignalRecordWriter, Protocol):
    """Additive capability for writers of enriched visual acceptances."""

    def write_accepted(
        self, record: SignalRecord, evidence: AcceptedSignalEvidence
    ) -> None:
        """Persist the accepted signal and same-evaluation evidence together."""
