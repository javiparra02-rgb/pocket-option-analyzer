from __future__ import annotations

import numpy as np


class FrameValidator:
    """
    Valida imágenes antes de iniciar el procesamiento.
    """

    @staticmethod
    def validate(image: np.ndarray) -> bool:
        """
        Comprueba si la imagen es válida para el pipeline.

        Parameters
        ----------
        image:
            Imagen a validar.

        Returns
        -------
        bool
        """
        if image is None:
            return False

        if not isinstance(image, np.ndarray):
            return False

        if image.size == 0:
            return False

        if image.ndim != 3:
            return False

        channels = image.shape[2]

        return channels in (3, 4)
