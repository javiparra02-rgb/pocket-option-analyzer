from __future__ import annotations

import numpy as np

from pocket_option_analyzer.vision.preprocessing import FrameValidator


def require_valid_chart_region_image(
    image: np.ndarray,
) -> np.ndarray:
    """
    Verifica el contrato visual común de los extractores de región.

    Los extractores aceptan únicamente imágenes uint8 BGR o BGRA con
    dimensiones espaciales positivas.

    Parameters
    ----------
    image:
        Imagen que será utilizada para calcular una región.

    Returns
    -------
    numpy.ndarray
        La misma imagen después de validar su estructura.

    Raises
    ------
    ValueError
        Cuando la imagen no cumple el contrato visual.
    """

    if not FrameValidator.validate(
        image,
    ):
        raise ValueError(
            "Chart region extractor requires a valid uint8 BGR or BGRA image."
        )

    return image
