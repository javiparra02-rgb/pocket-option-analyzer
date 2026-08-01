from __future__ import annotations

from dataclasses import dataclass

from pocket_option_analyzer.application.signals import (
    SignalGateAuditSnapshot,
)
from pocket_option_analyzer.domain.signals import (
    SignalRecordDisposition,
)


@dataclass(
    frozen=True,
    slots=True,
)
class SignalGateAuditViewModel:
    """
    Modelo visual de la auditoría acumulada del gate.
    """

    text: str

    css_class: str


class SignalGateAuditPresenter:
    """
    Formatea el estado acumulado del gate S30 para la GUI.
    """

    CSS_NEUTRAL = "gate-neutral"
    CSS_ACCEPTED = "gate-accepted"
    CSS_SUPPRESSED = "gate-suppressed"

    def present(
        self,
        snapshot: SignalGateAuditSnapshot,
    ) -> SignalGateAuditViewModel:

        return SignalGateAuditViewModel(
            text=(
                "Gate S30 (ejecución): "
                f"{snapshot.accepted_count} "
                f"{self._accepted_label(snapshot.accepted_count)}"
                " | "
                f"{snapshot.duplicate_suppressed_count} "
                f"{self._suppressed_label(
                    snapshot.duplicate_suppressed_count
                )}"
                " | "
                f"{self._last_event_label(snapshot)}"
            ),
            css_class=self._css_class(
                snapshot=snapshot,
            ),
        )

    @staticmethod
    def _accepted_label(
        count: int,
    ) -> str:
        return (
            "aceptada"
            if count == 1
            else "aceptadas"
        )

    @staticmethod
    def _suppressed_label(
        count: int,
    ) -> str:
        return (
            "duplicada suprimida"
            if count == 1
            else "duplicadas suprimidas"
        )

    def _last_event_label(
        self,
        snapshot: SignalGateAuditSnapshot,
    ) -> str:

        if (
            snapshot.last_disposition is None
            or snapshot.last_direction is None
            or snapshot.last_interval_started_at is None
        ):
            return "último: -"

        direction_label = (
            snapshot.last_direction.name
        )

        if (
            snapshot.last_disposition
            is SignalRecordDisposition.ACTIONABLE_ACCEPTED
        ):
            event_label = "aceptada"
        else:
            event_label = "suprimida"

        interval_label = (
            snapshot.last_interval_started_at.strftime(
                "%H:%M:%S",
            )
        )

        return (
            f"último: {direction_label} {event_label}"
            f" | vela {interval_label}"
        )

    def _css_class(
        self,
        snapshot: SignalGateAuditSnapshot,
    ) -> str:

        if (
            snapshot.last_disposition
            is SignalRecordDisposition.DUPLICATE_SUPPRESSED
        ):
            return self.CSS_SUPPRESSED

        if (
            snapshot.last_disposition
            is SignalRecordDisposition.ACTIONABLE_ACCEPTED
        ):
            return self.CSS_ACCEPTED

        return self.CSS_NEUTRAL