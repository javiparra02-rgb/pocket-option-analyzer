from __future__ import annotations

import logging

from PySide6.QtCore import QLocale
from PySide6.QtTextToSpeech import QTextToSpeech

logger = logging.getLogger(__name__)


class QtTextToSpeechAdapter:
    """
    Adaptador de voz basado en QTextToSpeech.

    Usa el motor de voz disponible en Windows y configura una
    localización en español. Si el motor falla, registra el problema
    sin detener la aplicación.
    """

    DEFAULT_LOCALE = "es-CL"
    DEFAULT_RATE = 0.0
    DEFAULT_VOLUME = 1.0

    def __init__(
        self,
        synthesizer: QTextToSpeech | None = None,
        locale_name: str = DEFAULT_LOCALE,
        rate: float = DEFAULT_RATE,
        volume: float = DEFAULT_VOLUME,
    ) -> None:
        self._synthesizer = synthesizer or QTextToSpeech()

        self._synthesizer.setLocale(
            QLocale(locale_name),
        )
        self._synthesizer.setRate(
            rate,
        )
        self._synthesizer.setVolume(
            volume,
        )

    def speak(
        self,
        text: str,
    ) -> None:
        normalized_text = text.strip()

        if not normalized_text:
            return

        try:
            self._synthesizer.say(
                normalized_text,
            )
        except RuntimeError:
            logger.exception(
                "No fue posible reproducir la notificación de voz: %s",
                normalized_text,
            )