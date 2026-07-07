from __future__ import annotations

from pocket_option_analyzer.domain.signals import (
    SignalDirection,
    SignalRecord,
    SignalStrength,
)
from pocket_option_analyzer.presentation.signals.signal_record_view_model import (
    SignalRecordViewModel,
)


class SignalRecordPresenter:
    """
    Convierte SignalRecord en un ViewModel listo para la GUI.

    No analiza mercado.
    No genera señales.
    No interactúa con Pocket Option.
    Solo adapta datos del dominio a presentación.
    """

    def present(
        self,
        record: SignalRecord,
    ) -> SignalRecordViewModel:

        return SignalRecordViewModel(
            direction_label=self._direction_label(
                direction=record.signal.direction,
            ),
            strength_label=self._strength_label(
                strength=record.signal.strength,
            ),
            reason=record.signal.reason,
            source=record.source,
            created_at_label=record.created_at.strftime(
                "%Y-%m-%d %H:%M:%S",
            ),
            is_actionable=record.is_actionable,
            css_class=self._css_class(
                direction=record.signal.direction,
            ),
        )

    def _direction_label(
        self,
        direction: SignalDirection,
    ) -> str:

        if direction is SignalDirection.CALL:
            return "CALL"

        if direction is SignalDirection.PUT:
            return "PUT"

        return "SIN SEÑAL"

    def _strength_label(
        self,
        strength: SignalStrength,
    ) -> str:

        if strength is SignalStrength.HIGH:
            return "ALTA"

        if strength is SignalStrength.MEDIUM:
            return "MEDIA"

        if strength is SignalStrength.LOW:
            return "BAJA"

        return "NINGUNA"

    def _css_class(
        self,
        direction: SignalDirection,
    ) -> str:

        if direction is SignalDirection.CALL:
            return "signal-call"

        if direction is SignalDirection.PUT:
            return "signal-put"

        return "signal-neutral"