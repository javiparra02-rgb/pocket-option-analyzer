from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SessionRiskViewModel:
    """
    Modelo visual informativo del riesgo de sesión.

    No bloquea operaciones.
    No ejecuta acciones.
    Solo entrega texto y estado para la GUI.
    """

    text: str
    state: str


class SessionRiskPresenter:
    """
    Construye el mensaje visual de riesgo de sesión.

    La app no conoce resultados manuales de ganancia o pérdida.
    Por eso este panel solo recuerda límites operativos generales.
    """

    STATE_OK = "OK"
    STATE_WARNING = "WARNING"
    STATE_LIMIT_REACHED = "LIMIT_REACHED"

    DEFAULT_MAX_SESSION_SIGNALS = 12
    DEFAULT_WARNING_SIGNAL_COUNT = 10

    MANUAL_LOSS_REMINDER = (
        "Recordatorio: detener si acumulas 3 pérdidas manuales"
    )

    def __init__(
        self,
        max_session_signals: int = DEFAULT_MAX_SESSION_SIGNALS,
        warning_signal_count: int = DEFAULT_WARNING_SIGNAL_COUNT,
    ) -> None:
        self._max_session_signals = max_session_signals
        self._warning_signal_count = warning_signal_count

    def present(
        self,
        total_confirmed_signals: int,
    ) -> SessionRiskViewModel:
        if total_confirmed_signals >= self._max_session_signals:
            return SessionRiskViewModel(
                text=(
                    "Riesgo sesión: LÍMITE ALCANZADO | "
                    f"Señales confirmadas: {total_confirmed_signals}/"
                    f"{self._max_session_signals} | "
                    "No buscar más entradas en esta sesión"
                ),
                state=self.STATE_LIMIT_REACHED,
            )

        if total_confirmed_signals >= self._warning_signal_count:
            return SessionRiskViewModel(
                text=(
                    "Riesgo sesión: ATENCIÓN | "
                    f"Señales confirmadas: {total_confirmed_signals}/"
                    f"{self._max_session_signals} | "
                    "Considera reducir operaciones"
                ),
                state=self.STATE_WARNING,
            )

        return SessionRiskViewModel(
            text=(
                "Riesgo sesión: OK | "
                f"Señales confirmadas: {total_confirmed_signals}/"
                f"{self._max_session_signals} | "
                f"{self.MANUAL_LOSS_REMINDER}"
            ),
            state=self.STATE_OK,
        )