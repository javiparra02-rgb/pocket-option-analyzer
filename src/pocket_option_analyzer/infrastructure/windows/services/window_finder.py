from __future__ import annotations

from collections.abc import Callable

from pocket_option_analyzer.infrastructure.windows.models import (
    Win32WindowInfo,
)

from .window_enumerator import WindowEnumerator


class WindowFinder:
    """
    Servicio encargado de localizar ventanas.
    """

    def __init__(
        self,
        enumerator: WindowEnumerator,
    ) -> None:
        self._enumerator = enumerator

    def find(
        self,
        title: str,
    ) -> Win32WindowInfo | None:
        """
        Busca una ventana cuyo título contenga el texto indicado.
        """

        title = title.lower()

        for window in self._enumerator.enumerate():

            if title in window.title.lower():
                return window

        return None

    def find_first(
        self,
        predicate: Callable[[Win32WindowInfo], bool],
    ) -> Win32WindowInfo | None:
        """
        Busca utilizando un predicado.
        """

        for window in self._enumerator.enumerate():

            if predicate(window):
                return window

        return None