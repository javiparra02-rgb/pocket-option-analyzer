from __future__ import annotations

import cv2
import numpy as np


class ImageNormalizer:
    """
    Normaliza imágenes para el pipeline de visión.

    Centraliza todas las operaciones de preprocesamiento
    que deben ejecutarse antes del análisis.
    """

    def normalize(
        self,
        image: np.ndarray,
    ) -> np.ndarray:
        """
        Devuelve una copia normalizada de la imagen.
        """

        image = image.copy()

        image = cv2.GaussianBlur(
            image,
            (3, 3),
            0,
        )

        return image