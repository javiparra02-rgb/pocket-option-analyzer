from __future__ import annotations

import numpy as np

from pocket_option_analyzer.vision.models import ChartRegion


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

        Raises
        ------
        ValueError
            Cuando la imagen o la región no tienen dimensiones válidas,
            o cuando el ROI excede los límites de la imagen.
        """

        if image.ndim < 2:
            raise ValueError("Image must have at least two dimensions.")

        region = ChartRegion(
            x=x,
            y=y,
            width=width,
            height=height,
        )

        if region.x < 0 or region.y < 0:
            raise ValueError("ROI coordinates cannot be negative.")

        if not region.has_positive_area:
            raise ValueError("ROI dimensions must be greater than zero.")

        if not region.fits_within(
            image_width=int(
                image.shape[1],
            ),
            image_height=int(
                image.shape[0],
            ),
        ):
            raise ValueError("ROI must fit entirely within image bounds.")

        return image[
            region.y : region.bottom,
            region.x : region.right,
        ].copy(
            order="C",
        )
