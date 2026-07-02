from __future__ import annotations

from typing import Optional

import pygetwindow as gw

from pocket_option_analyzer.infrastructure.capture.models import WindowInfo


class Win32WindowLocator:
    """
    Localiza la ventana de Pocket Option utilizando la API de Windows
    a través de pygetwindow.
    """

    def find(self, window_title: str) -> Optional[WindowInfo]:
        """
        Busca una ventana cuyo título contenga el texto indicado.

        Parameters
        ----------
        window_title:
            Texto que debe contener el título de la ventana.

        Returns
        -------
        WindowInfo | None
        """

        windows = gw.getWindowsWithTitle(window_title)

        if not windows:
            return None

        window = windows[0]

        return WindowInfo(
            title=window.title,
            left=window.left,
            top=window.top,
            width=window.width,
            height=window.height,
        )