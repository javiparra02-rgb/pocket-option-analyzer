from __future__ import annotations

import cv2
import numpy as np


class ImageConverter:
    """
    Conversión entre formatos de imagen utilizados por el proyecto.
    """

    @staticmethod
    def bgra_to_bgr(image: np.ndarray) -> np.ndarray:
        """
        Convierte una imagen BGRA a BGR.

        Parameters
        ----------
        image:
            Imagen BGRA.

        Returns
        -------
        numpy.ndarray
            Imagen BGR.
        """
        return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
