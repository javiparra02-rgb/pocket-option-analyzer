from __future__ import annotations

import mss
import numpy as np


class MSSCaptureAdapter:
    """
    Adaptador para capturar una región de pantalla utilizando MSS.

    Esta clase es stateless: no mantiene recursos abiertos entre llamadas.
    """

    def capture(self, region: ChartRegion) -> np.ndarray:
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
            "left": region.left,
            "top": region.top,
            "width": region.width,
            "height": region.height,
        }

        with mss.MSS() as sct:
            print("========== MSS REGION ==========")
            print(monitor)
            print("===============================\n")
            image = sct.grab(monitor)

        return np.asarray(image)
