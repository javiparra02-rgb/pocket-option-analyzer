from __future__ import annotations

import mss
import numpy as np

from pocket_option_analyzer.infrastructure.capture.models import WindowInfo


class MSSCaptureAdapter:
    """
    Adaptador para capturar una región de pantalla utilizando MSS.
    """

    def __init__(self) -> None:
        self._sct = mss.MSS()

    def capture(self, window: WindowInfo) -> np.ndarray:
        """
        Captura la región correspondiente a la ventana indicada.
        """
        monitor = {
            "left": window.left,
            "top": window.top,
            "width": window.width,
            "height": window.height,
        }

        image = self._sct.grab(monitor)

        return np.array(image)