from __future__ import annotations

from enum import Enum


class SignalRecordDisposition(str, Enum):
    """
    Clasifica cómo debe tratarse un registro de señal.

    OBSERVED:
        Análisis neutral o registro anterior a la incorporación del gate.

    ACTIONABLE_ACCEPTED:
        Primera CALL o PUT aceptada dentro de una vela.

    DUPLICATE_SUPPRESSED:
        CALL o PUT posterior dentro de la misma vela de 30 segundos.
    """

    OBSERVED = "observed"
    ACTIONABLE_ACCEPTED = "actionable_accepted"
    DUPLICATE_SUPPRESSED = "duplicate_suppressed"
