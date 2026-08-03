from __future__ import annotations

import mss
import numpy as np

from pocket_option_analyzer.infrastructure.capture.models import (
    WindowInfo,
)


class MSSCaptureAdapter:
    """
    Adaptador para capturar una región de pantalla utilizando MSS.

    La clase no conserva recursos nativos ni capturas entre llamadas.
    Cada sesión MSS se abre y cierra dentro de capture().
    """

    def capture(
        self,
        window: WindowInfo,
    ) -> np.ndarray:
        """
        Captura la región de pantalla indicada.

        Parameters
        ----------
        window:
            Región rectangular de la ventana.

        Returns
        -------
        numpy.ndarray
            Copia independiente de la captura en formato BGRA.
        """

        monitor = {
            "left": window.left,
            "top": window.top,
            "width": window.width,
            "height": window.height,
        }

        with mss.MSS() as screen_capture:
            screenshot = screen_capture.grab(
                monitor,
            )

        return np.array(
            screenshot,
            copy=True,
        )
