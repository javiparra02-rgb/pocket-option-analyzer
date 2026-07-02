from __future__ import annotations

from typing import Protocol

from pocket_option_analyzer.infrastructure.capture.models import WindowInfo


class WindowLocator(Protocol):
    """
    Contrato para localizar ventanas del sistema.
    """

    def find(self, window_title: str) -> WindowInfo | None:
        """
        Busca una ventana por su título.

        Returns
        -------
        WindowInfo | None
            Información de la ventana o None si no existe.
        """
        ...