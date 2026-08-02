from __future__ import annotations

from dataclasses import dataclass

from pocket_option_analyzer.presentation.signals.signal_record_presenter import (
    SignalRecordViewModel,
)


@dataclass(frozen=True)
class OperationalSummaryViewModel:
    """
    Modelo visual del resumen operativo.

    No decide señales.
    Solo clasifica el texto operativo para que la GUI pueda aplicar
    estilos de forma simple.
    """

    text: str
    target_direction: str
    state: str


class OperationalSummaryPresenter:
    """
    Clasifica el resumen operativo para la GUI.

    No analiza mercado.
    No calcula indicadores.
    No decide entradas.
    """

    STATE_WAITING = "WAITING"
    STATE_WATCH = "WATCH"
    STATE_CONFIRMED = "CONFIRMED"

    DIRECTION_CALL = "CALL"
    DIRECTION_PUT = "PUT"
    DIRECTION_NONE = "NONE"

    def present(
        self,
        view_model: SignalRecordViewModel,
    ) -> OperationalSummaryViewModel:
        summary_text = view_model.operational_summary_label
        normalized_summary = summary_text.upper()
        normalized_direction = view_model.direction_label.upper()

        target_direction = self._resolve_target_direction(
            summary_text=normalized_summary,
            direction=normalized_direction,
            is_actionable=view_model.is_actionable,
        )
        state = self._resolve_state(
            summary_text=normalized_summary,
            target_direction=target_direction,
            is_actionable=view_model.is_actionable,
        )

        return OperationalSummaryViewModel(
            text=summary_text,
            target_direction=target_direction,
            state=state,
        )

    def _resolve_target_direction(
        self,
        summary_text: str,
        direction: str,
        is_actionable: bool,
    ) -> str:
        if is_actionable and direction in {
            self.DIRECTION_CALL,
            self.DIRECTION_PUT,
        }:
            return direction

        if "CALL" in summary_text:
            return self.DIRECTION_CALL

        if "PUT" in summary_text:
            return self.DIRECTION_PUT

        return self.DIRECTION_NONE

    def _resolve_state(
        self,
        summary_text: str,
        target_direction: str,
        is_actionable: bool,
    ) -> str:
        if is_actionable and target_direction in {
            self.DIRECTION_CALL,
            self.DIRECTION_PUT,
        }:
            return self.STATE_CONFIRMED

        if "ENTRADA" in summary_text and target_direction in {
            self.DIRECTION_CALL,
            self.DIRECTION_PUT,
        }:
            return self.STATE_CONFIRMED

        if "VIGILAR" in summary_text and target_direction in {
            self.DIRECTION_CALL,
            self.DIRECTION_PUT,
        }:
            return self.STATE_WATCH

        return self.STATE_WAITING
