from __future__ import annotations

from typing import Iterable

from pocket_option_analyzer.infrastructure.capture.models import WindowInfo

from .window_enumerator import WindowEnumerator


class Win32WindowLocator:
    """
    Localiza una ventana utilizando coincidencias parciales
    sobre las ventanas visibles del sistema.
    """

    def __init__(
        self,
        enumerator: WindowEnumerator | None = None,
    ) -> None:
        self._enumerator = enumerator or WindowEnumerator()

    def find(self, window_title: str) -> WindowInfo | None:
        """
        Busca la mejor coincidencia.

        Parameters
        ----------
        window_title:
            Texto a buscar.

        Returns
        -------
        WindowInfo | None
        """

        candidates = list(self._enumerator.enumerate())

        if not candidates:
            return None

        search = window_title.lower()

        matches = [
            window
            for window in candidates
            if search in window.title.lower()
        ]

        if not matches:
            return None

        matches.sort(
            key=lambda window: window.width * window.height,
            reverse=True,
        )

        return matches[0]