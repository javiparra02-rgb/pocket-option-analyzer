from __future__ import annotations

import cv2
import numpy as np


class PocketOptionCurrentPriceMaskBuilder:
    """
    Construye una mascara binaria para la guia del precio actual.

    Los limites HSV son parametros diagnosticos iniciales basados en muestras
    visuales de Pocket Option. No constituyen una calibracion final.
    """

    def __init__(
        self,
        min_hue: int = 95,
        max_hue: int = 120,
        min_saturation: int = 70,
        max_saturation: int = 160,
        min_value: int = 90,
        max_value: int = 170,
    ) -> None:
        self._validate_range("hue", min_hue, max_hue, 180)
        self._validate_range(
            "saturation",
            min_saturation,
            max_saturation,
            255,
        )
        self._validate_range("value", min_value, max_value, 255)

        self._lower = np.array(
            [min_hue, min_saturation, min_value],
            dtype=np.uint8,
        )
        self._upper = np.array(
            [max_hue, max_saturation, max_value],
            dtype=np.uint8,
        )

    def build(
        self,
        image: np.ndarray,
    ) -> np.ndarray:
        """Devuelve una mascara binaria para la guia azul grisacea."""

        if image.ndim == 3 and image.shape[2] == 4:
            image = cv2.cvtColor(
                image,
                cv2.COLOR_BGRA2BGR,
            )

        hsv = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2HSV,
        )

        return cv2.inRange(
            hsv,
            self._lower,
            self._upper,
        )

    @staticmethod
    def _validate_range(
        name: str,
        minimum: int,
        maximum: int,
        allowed_maximum: int,
    ) -> None:
        if not isinstance(minimum, int) or not isinstance(maximum, int):
            raise TypeError(f"{name} limits must be integers")
        if not 0 <= minimum <= maximum <= allowed_maximum:
            raise ValueError(
                f"{name} limits must satisfy "
                f"0 <= minimum <= maximum <= {allowed_maximum}"
            )
