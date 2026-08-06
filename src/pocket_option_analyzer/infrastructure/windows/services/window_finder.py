from __future__ import annotations

from collections.abc import Callable, Iterator

from pocket_option_analyzer.infrastructure.errors import (
    CaptureUnavailableError,
)
from pocket_option_analyzer.infrastructure.windows.models import (
    Win32WindowInfo,
)

from .window_enumerator import WindowEnumerator
from .window_reader import WindowReader


class WindowFinder:
    """
    Servicio encargado de localizar ventanas capturables.

    La enumeración obtiene únicamente HWND. Cada candidato se vuelve
    a leer mediante WindowReader antes de evaluarlo.
    """

    def __init__(
        self,
        enumerator: WindowEnumerator,
        reader: WindowReader,
    ) -> None:
        self._enumerator = enumerator
        self._reader = reader

    def find(
        self,
        title: str,
    ) -> Win32WindowInfo | None:
        """
        Devuelve la ventana capturable más grande cuyo título coincida.

        La comparación no distingue mayúsculas de minúsculas.
        Ventanas que desaparecen durante la búsqueda se omiten.
        """

        search = title.strip().casefold()

        if not search:
            return None

        return max(
            (
                window
                for window in self._iter_capture_candidates()
                if search in window.title.casefold()
            ),
            key=lambda window: window.area,
            default=None,
        )

    def find_first(
        self,
        predicate: Callable[
            [Win32WindowInfo],
            bool,
        ],
    ) -> Win32WindowInfo | None:
        """
        Devuelve el primer candidato capturable que cumple el predicado.
        """

        for window in self._iter_capture_candidates():
            if predicate(
                window,
            ):
                return window

        return None

    def _iter_capture_candidates(
        self,
    ) -> Iterator[Win32WindowInfo]:
        """
        Resuelve HWND y descarta candidatos temporalmente no disponibles.
        """

        for hwnd in self._enumerator.enumerate_hwnds():
            try:
                window = self._reader.read(
                    hwnd,
                )
            except CaptureUnavailableError:
                continue

            if window.is_capture_candidate:
                yield window
