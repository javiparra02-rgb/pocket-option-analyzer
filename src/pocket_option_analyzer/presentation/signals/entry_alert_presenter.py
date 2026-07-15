from __future__ import annotations

from dataclasses import dataclass

from pocket_option_analyzer.presentation.signals.signal_record_presenter import (
    SignalRecordViewModel,
)


@dataclass(frozen=True)
class EntryAlertViewModel:
    """
    Modelo visual para la alerta destacada de entrada confirmada.
    """

    text: str
    target_direction: str
    is_visible: bool


class EntryAlertPresenter:
    """
    Construye la alerta visual de entrada confirmada.

    No decide señales.
    No analiza mercado.
    Solo transforma un SignalRecordViewModel en una alerta visible
    para la GUI.
    """

    def present(
        self,
        view_model: SignalRecordViewModel,
    ) -> EntryAlertViewModel:
        direction = view_model.direction_label.upper()

        if not view_model.is_actionable:
            return EntryAlertViewModel(
                text="",
                target_direction="NONE",
                is_visible=False,
            )

        if direction == "CALL":
            return EntryAlertViewModel(
                text="ENTRADA CALL CONFIRMADA",
                target_direction="CALL",
                is_visible=True,
            )

        if direction == "PUT":
            return EntryAlertViewModel(
                text="ENTRADA PUT CONFIRMADA",
                target_direction="PUT",
                is_visible=True,
            )

        return EntryAlertViewModel(
            text="",
            target_direction="NONE",
            is_visible=False,
        )