from __future__ import annotations

import numpy as np


class RegionExtractor:
    """
    Extrae una región rectangular completamente contenida en una imagen.

    El resultado es una copia independiente y contigua, por lo que no
    conserva en memoria la matriz completa de origen.
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
        Extrae una región de interés válida.

        Parameters
        ----------
        image:
            Imagen de entrada.
        x:
            Coordenada horizontal inicial.
        y:
            Coordenada vertical inicial.
        width:
            Ancho de la región.
        height:
            Alto de la región.

        Returns
        -------
        numpy.ndarray
            Copia independiente y C-contiguous de la región.

        Raises
        ------
        ValueError
            Cuando la imagen o la región no tienen dimensiones válidas,
            o cuando el ROI excede los límites de la imagen.
        """

        if image.ndim < 2:
            raise ValueError("Image must have at least two dimensions.")

        if x < 0 or y < 0:
            raise ValueError("ROI coordinates cannot be negative.")

        if width <= 0 or height <= 0:
            raise ValueError("ROI dimensions must be greater than zero.")

        image_height = int(
            image.shape[0],
        )
        image_width = int(
            image.shape[1],
        )

        region_right = x + width
        region_bottom = y + height

        if region_right > image_width or region_bottom > image_height:
            raise ValueError("ROI must fit entirely within image bounds.")

        return image[
            y:region_bottom,
            x:region_right,
        ].copy(
            order="C",
        )
