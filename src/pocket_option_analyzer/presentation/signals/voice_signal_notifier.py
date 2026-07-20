from __future__ import annotations

from typing import Protocol

from pocket_option_analyzer.presentation.signals.signal_record_presenter import (
    SignalRecordViewModel,
)


class SpeechEngine(Protocol):
    """
    Contrato mínimo para un motor de voz.

    La capa de presentación no conoce QTextToSpeech ni detalles
    específicos del sistema operativo.
    """

    def speak(
        self,
        text: str,
    ) -> None:
        """
        Reproduce verbalmente el texto recibido.
        """


class VoiceSignalNotifier:
    """
    Emite mensajes de voz para señales confirmadas.

    CALL confirmada -> "Compra".
    PUT confirmada -> "Vende".

    No anuncia señales de vigilancia ni estados de espera.
    Tampoco repite continuamente una misma señal activa.
    """

    CALL_MESSAGE = "Compra"
    PUT_MESSAGE = "Vende"

    TEST_MESSAGE = "Notificaciones activadas"

    VALID_DIRECTIONS = {
        "CALL",
        "PUT",
    }

    def __init__(
        self,
        speech_engine: SpeechEngine,
        enabled: bool = True,
    ) -> None:
        self._speech_engine = speech_engine
        self._enabled = enabled
        self._active_direction: str | None = None

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    @property
    def active_direction(self) -> str | None:
        return self._active_direction

    def set_enabled(
        self,
        enabled: bool,
    ) -> None:
        self._enabled = enabled

        if not enabled:
            self.reset()

    def notify(
        self,
        view_model: SignalRecordViewModel,
    ) -> None:
        """
        Revisa el estado presentado y anuncia una señal nueva.

        Una señal continua solo se anuncia una vez. Cuando el sistema
        vuelve a SIN SEÑAL, queda preparado para anunciar otra entrada.
        """

        direction = view_model.direction_label.strip().upper()

        if not view_model.is_actionable:
            self.reset()
            return

        if direction not in self.VALID_DIRECTIONS:
            self.reset()
            return

        if not self._enabled:
            return

        if direction == self._active_direction:
            return

        self._active_direction = direction

        if direction == "CALL":
            self._speech_engine.speak(
                self.CALL_MESSAGE,
            )
            return

        self._speech_engine.speak(
            self.PUT_MESSAGE,
        )

    def test_voice(
        self,
    ) -> None:
        """
        Reproduce un mensaje para verificar el funcionamiento del audio.

        No altera la dirección activa ni el control de duplicados.
        """

        if not self._enabled:
            return

        self._speech_engine.speak(
            self.TEST_MESSAGE,
        )

    def reset(self) -> None:
        """
        Permite que la siguiente señal confirmada vuelva a anunciarse.
        """

        self._active_direction = None