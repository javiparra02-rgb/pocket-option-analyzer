from __future__ import annotations

from dataclasses import dataclass

from pocket_option_analyzer.presentation.signals.signal_record_presenter import (
    SignalRecordViewModel,
)


@dataclass(frozen=True)
class ConfirmationChecklistViewModel:
    """
    Modelo visual compacto del checklist de confirmación.

    No decide señales.
    Solo representa, para la GUI, qué partes del análisis están listas.
    """

    text: str
    target_direction: str
    is_actionable: bool


class ConfirmationChecklistPresenter:
    """
    Construye el checklist compacto de confirmación para la GUI.

    Este presenter interpreta textos ya generados por la capa de presentación.
    No calcula indicadores.
    No analiza imágenes.
    No decide entradas.
    """

    def present(
        self,
        view_model: SignalRecordViewModel,
    ) -> ConfirmationChecklistViewModel:
        summary_text = view_model.operational_summary_label.upper()
        visual_text = view_model.visual_diagnostics_label.upper()
        indicator_text = view_model.indicator_diagnostics_label.upper()
        direction = view_model.direction_label.upper()

        target_direction = self._resolve_direction(
            summary_text=summary_text,
            visual_text=visual_text,
            direction=direction,
            is_actionable=view_model.is_actionable,
        )

        visual_ok = self._check_visual_confirmation(
            visual_text=visual_text,
            is_actionable=view_model.is_actionable,
        )
        ema_ok = self._check_ema_confirmation(
            target_direction=target_direction,
            indicator_text=indicator_text,
        )
        rsi_ok = self._check_rsi_confirmation(
            target_direction=target_direction,
            indicator_text=indicator_text,
        )
        stochastic_ok = self._check_stochastic_confirmation(
            target_direction=target_direction,
            indicator_text=indicator_text,
        )

        entry_label = (
            target_direction
            if view_model.is_actionable and target_direction in {"CALL", "PUT"}
            else "ESPERAR"
        )

        checklist_text = (
            f"Visual: {self._check_icon(visual_ok)} | "
            f"EMA: {self._check_icon(ema_ok)} | "
            f"RSI: {self._check_icon(rsi_ok)} | "
            f"Stoch: {self._check_icon(stochastic_ok)} | "
            f"Entrada: {entry_label}"
        )

        return ConfirmationChecklistViewModel(
            text=checklist_text,
            target_direction=target_direction,
            is_actionable=view_model.is_actionable,
        )

    def _resolve_direction(
        self,
        summary_text: str,
        visual_text: str,
        direction: str,
        is_actionable: bool,
    ) -> str:
        if is_actionable and direction in {"CALL", "PUT"}:
            return direction

        if "CALL" in summary_text or "VIGILAR_CALL" in visual_text:
            return "CALL"

        if "PUT" in summary_text or "VIGILAR_PUT" in visual_text:
            return "PUT"

        return "NONE"

    def _check_visual_confirmation(
        self,
        visual_text: str,
        is_actionable: bool,
    ) -> bool:
        if is_actionable:
            return True

        return "SEÑAL_CONFIRMADA" in visual_text

    def _check_ema_confirmation(
        self,
        target_direction: str,
        indicator_text: str,
    ) -> bool:
        if "INSUFICIENTE" in indicator_text:
            return False

        if target_direction == "CALL":
            return "EMA: ALCISTA" in indicator_text and "SUFICIENTE" in indicator_text

        if target_direction == "PUT":
            return "EMA: BAJISTA" in indicator_text and "SUFICIENTE" in indicator_text

        return False

    def _check_rsi_confirmation(
        self,
        target_direction: str,
        indicator_text: str,
    ) -> bool:
        if target_direction == "CALL":
            return "CALL EN RANGO" in indicator_text

        if target_direction == "PUT":
            return "PUT EN RANGO" in indicator_text

        return False

    def _check_stochastic_confirmation(
        self,
        target_direction: str,
        indicator_text: str,
    ) -> bool:
        if target_direction == "CALL":
            return "CRUCE ALCISTA" in indicator_text

        if target_direction == "PUT":
            return "CRUCE BAJISTA" in indicator_text

        return False

    def _check_icon(
        self,
        confirmed: bool,
    ) -> str:
        return "✅" if confirmed else "❌"
