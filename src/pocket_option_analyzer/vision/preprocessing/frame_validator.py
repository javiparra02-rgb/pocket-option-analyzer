from __future__ import annotations

import numpy as np


class FrameValidator:
    """
    Valida imágenes antes de iniciar el procesamiento.

    El contrato visual del proyecto utiliza imágenes uint8 con tres
    canales BGR o cuatro canales BGRA.
    """

    @staticmethod
    def validate(
        image: object,
    ) -> bool:
        """
        Comprueba si una imagen cumple el contrato del pipeline.

        La validación inspecciona únicamente metadatos de la matriz.
        No recorre ni copia sus píxeles.

        Parameters
        ----------
        image:
            Objeto que debe representar una imagen NumPy.

        Returns
        -------
        bool
            True cuando la imagen es válida.
        """

        if not isinstance(
            image,
            np.ndarray,
        ):
            return False

        if image.ndim != 3:
            return False

        height, width, channels = image.shape

        if height <= 0 or width <= 0:
            return False

        if channels not in (
            3,
            4,
        ):
            return False

        return image.dtype == np.dtype(
            np.uint8,
        )
