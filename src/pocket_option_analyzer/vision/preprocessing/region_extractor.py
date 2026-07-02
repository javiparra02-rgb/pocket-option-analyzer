from __future__ import annotations

import numpy as np


class RegionExtractor:
    """
    Extrae una región rectangular de una imagen.
    """

    @staticmethod
    def extract(
        image: np.ndarray,
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> np.ndarray:
        """
        Extrae una región de interés (ROI).

        Parameters
        ----------
        image:
            Imagen de entrada.
        x:
            Coordenada X inicial.
        y:
            Coordenada Y inicial.
        width:
            Ancho de la región.
        height:
            Alto de la región.

        Returns
        -------
        numpy.ndarray
            Región extraída.
        """
        return image[y:y + height, x:x + width]