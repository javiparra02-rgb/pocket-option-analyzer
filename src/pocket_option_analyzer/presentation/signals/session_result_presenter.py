from __future__ import annotations

from dataclasses import dataclass

from pocket_option_analyzer.presentation.signals.session_result_tracker import (
    SessionResultSnapshot,
)


@dataclass(frozen=True)
class SessionResultViewModel:
    """
    Representación visual de los resultados manuales.
    """

    text: str
    compact_text: str
    pause_alert_text: str
    pause_recommended: bool


class SessionResultPresenter:
    """
    Convierte el estado de resultados en textos para la GUI.
    """

    PAUSE_ALERT_TITLE = "PAUSA RECOMENDADA"

    def present(
        self,
        snapshot: SessionResultSnapshot,
    ) -> SessionResultViewModel:
        rate_text = self._format_rate(
            percentage=snapshot.win_rate_percentage,
        )

        text = (
            f"Resultados: {snapshot.wins} ganadas | "
            f"{snapshot.losses} perdidas | "
            f"Tasa observada: {rate_text} | "
            "Racha de pérdidas: "
            f"{snapshot.consecutive_losses}/"
            f"{snapshot.max_consecutive_losses}"
        )

        compact_text = (
            f"Resultados: {snapshot.wins}G | "
            f"{snapshot.losses}P | "
            f"{rate_text} | "
            "Racha: "
            f"{snapshot.consecutive_losses}/"
            f"{snapshot.max_consecutive_losses}"
        )

        pause_alert_text = ""

        if snapshot.pause_recommended:
            pause_alert_text = (
                f"{self.PAUSE_ALERT_TITLE}\n"
                "Se alcanzaron "
                f"{snapshot.max_consecutive_losses} pérdidas consecutivas\n"
                "Detén la sesión y revisa las operaciones"
            )

        return SessionResultViewModel(
            text=text,
            compact_text=compact_text,
            pause_alert_text=pause_alert_text,
            pause_recommended=snapshot.pause_recommended,
        )

    @staticmethod
    def _format_rate(
        percentage: float | None,
    ) -> str:
        if percentage is None:
            return "-"

        return (
            f"{percentage:.1f}".replace(
                ".",
                ",",
            )
            + " %"
        )
