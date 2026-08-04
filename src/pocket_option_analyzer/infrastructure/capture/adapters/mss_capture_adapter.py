from __future__ import annotations

import mss
import numpy as np

from pocket_option_analyzer.infrastructure.capture.errors import (
    CaptureUnavailableError,
)
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

        Raises
        ------
        CaptureUnavailableError
            Cuando MSS no puede acceder temporalmente a la región.
        """

        monitor = {
            "left": window.left,
            "top": window.top,
            "width": window.width,
            "height": window.height,
        }

        try:
            with mss.MSS() as screen_capture:
                screenshot = screen_capture.grab(
                    monitor,
                )
        except mss.ScreenShotError as error:
            raise CaptureUnavailableError(
                "MSS could not capture the requested window region: "
                f"title={window.title!r}, "
                f"left={window.left}, "
                f"top={window.top}, "
                f"width={window.width}, "
                f"height={window.height}."
            ) from error

        return np.array(
            screenshot,
            copy=True,
        )
