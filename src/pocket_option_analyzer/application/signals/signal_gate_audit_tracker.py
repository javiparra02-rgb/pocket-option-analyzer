from __future__ import annotations

from dataclasses import dataclass
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
class SignalGateAuditSnapshot:
    """
    Estado acumulado del gate durante la ejecución actual.

    Solo contabiliza:

    - señales accionables aceptadas;
    - señales accionables duplicadas suprimidas.

    Los registros OBSERVED no alteran estos contadores.
    """

    accepted_count: int = 0

    duplicate_suppressed_count: int = 0

    last_disposition: SignalRecordDisposition | None = None

    last_direction: SignalDirection | None = None

    last_interval_started_at: datetime | None = None

    def __post_init__(
        self,
    ) -> None:
        if self.accepted_count < 0:
            raise ValueError("accepted_count no puede ser negativo.")

        if self.duplicate_suppressed_count < 0:
            raise ValueError("duplicate_suppressed_count no puede ser negativo.")

        has_last_event = self.last_disposition is not None

        last_event_fields_are_complete = (
            self.last_direction is not None
            and self.last_interval_started_at is not None
        )

        if has_last_event != last_event_fields_are_complete:
            raise ValueError(
                "Los datos del último evento deben estar completos o ausentes."
            )

        if self.last_disposition is None:
            return

        if self.last_disposition not in {
            SignalRecordDisposition.ACTIONABLE_ACCEPTED,
            SignalRecordDisposition.DUPLICATE_SUPPRESSED,
        }:
            raise ValueError(
                "El último evento debe ser una señal aceptada "
                "o una duplicada suprimida."
            )

        if self.last_direction is SignalDirection.NONE:
            raise ValueError("El último evento del gate no puede tener dirección NONE.")

        if (
            self.last_disposition is SignalRecordDisposition.ACTIONABLE_ACCEPTED
            and self.accepted_count < 1
        ):
            raise ValueError(
                "Una última señal aceptada requiere accepted_count mayor que cero."
            )

        if (
            self.last_disposition is SignalRecordDisposition.DUPLICATE_SUPPRESSED
            and self.duplicate_suppressed_count < 1
        ):
            raise ValueError(
                "Una última señal suprimida requiere "
                "duplicate_suppressed_count mayor que cero."
            )

    @property
    def total_actionable_attempts(
        self,
    ) -> int:
        return self.accepted_count + self.duplicate_suppressed_count


class SignalGateAuditTracker:
    """
    Acumula las decisiones observables del gate de señales.

    No decide si una señal debe aceptarse.
    Solo audita la disposición ya asignada al SignalRecord.
    """

    def __init__(
        self,
    ) -> None:
        self._accepted_count = 0
        self._duplicate_suppressed_count = 0

        self._last_disposition: SignalRecordDisposition | None = None

        self._last_direction: SignalDirection | None = None

        self._last_interval_started_at: datetime | None = None

    def track(
        self,
        record: SignalRecord,
    ) -> SignalGateAuditSnapshot:
        """
        Incorpora un SignalRecord a la auditoría.

        Los registros OBSERVED se ignoran y no modifican
        el último evento accionable.
        """

        if record.disposition is SignalRecordDisposition.OBSERVED:
            return self.snapshot()

        if record.disposition is SignalRecordDisposition.ACTIONABLE_ACCEPTED:
            self._accepted_count += 1

        elif record.disposition is SignalRecordDisposition.DUPLICATE_SUPPRESSED:
            self._duplicate_suppressed_count += 1

        else:
            return self.snapshot()

        self._last_disposition = record.disposition
        self._last_direction = record.signal.direction
        self._last_interval_started_at = record.candle_interval_started_at

        return self.snapshot()

    def snapshot(
        self,
    ) -> SignalGateAuditSnapshot:
        return SignalGateAuditSnapshot(
            accepted_count=self._accepted_count,
            duplicate_suppressed_count=(self._duplicate_suppressed_count),
            last_disposition=self._last_disposition,
            last_direction=self._last_direction,
            last_interval_started_at=(self._last_interval_started_at),
        )

    def reset(
        self,
    ) -> None:
        """
        Reinicia la auditoría de la ejecución.

        No debe confundirse con el reinicio visual de sesión.
        """

        self._accepted_count = 0
        self._duplicate_suppressed_count = 0
        self._last_disposition = None
        self._last_direction = None
        self._last_interval_started_at = None
