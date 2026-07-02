from __future__ import annotations

import mss
import numpy as np

from pocket_option_analyzer.infrastructure.capture.models import WindowInfo


class MSSCaptureAdapter:
    """
    Adaptador para capturar una región de pantalla utilizando MSS.

    Esta clase es stateless: no mantiene recursos abiertos entre llamadas.
    """

    def capture(self, window: WindowInfo) -> np.ndarray:
        """
        Captura la región indicada por WindowInfo.

        Parameters
        ----------
        window:
            Región de la ventana.

        Returns
        -------
        numpy.ndarray
            Imagen capturada en formato BGRA.
        """

        monitor = {
            "left": window.left,
            "top": window.top,
            "width": window.width,
            "height": window.height,
        }

        with mss.MSS() as sct:
            print("========== MSS REGION ==========")
            print(monitor)
            print("===============================\n")
            image = sct.grab(monitor)

        return np.asarray(image)