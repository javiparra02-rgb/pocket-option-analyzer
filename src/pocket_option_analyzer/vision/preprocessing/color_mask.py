from __future__ import annotations

import cv2
import numpy as np


class ColorMask:
    """
    Genera máscaras binarias a partir de rangos HSV.
    """

    def create(
        self,
        image: np.ndarray,
        lower: tuple[int, int, int],
        upper: tuple[int, int, int],
    ) -> np.ndarray:
        """
        Devuelve una máscara binaria.
        """

        lower_np = np.array(lower, dtype=np.uint8)
        upper_np = np.array(upper, dtype=np.uint8)

        return cv2.inRange(
            image,
            lower_np,
            upper_np,
        )