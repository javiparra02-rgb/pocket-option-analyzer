from __future__ import annotations

import cv2
import numpy as np


class BinaryMaskBuilder:
    """
    Construye una máscara binaria a partir de una imagen BGR.

    La máscara servirá posteriormente para detectar las velas del gráfico.
    """

    def build(
        self,
        image: np.ndarray,
    ) -> np.ndarray:
        """
        Convierte una imagen BGR en una máscara binaria.
        """

        gray = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2GRAY,
        )

        _, mask = cv2.threshold(
            gray,
            1,
            255,
            cv2.THRESH_BINARY,
        )

        return mask
