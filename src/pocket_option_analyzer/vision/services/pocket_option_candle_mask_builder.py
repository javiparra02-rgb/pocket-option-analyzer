from __future__ import annotations

import cv2
import numpy as np


class PocketOptionCandleMaskBuilder:
    """
    Construye una máscara binaria específica para velas de Pocket Option.

    Detecta principalmente:
    - velas blancas
    - velas rojas

    Ignora la mayor parte del fondo oscuro, cuadrícula y paneles.
    """

    def __init__(
        self,
        white_min_value: int = 180,
        white_max_saturation: int = 80,
        red_min_saturation: int = 80,
        red_min_value: int = 100,
        kernel_size: int = 3,
    ) -> None:
        self._white_min_value = white_min_value
        self._white_max_saturation = white_max_saturation
        self._red_min_saturation = red_min_saturation
        self._red_min_value = red_min_value
        self._kernel_size = kernel_size

    def build(
        self,
        image: np.ndarray,
    ) -> np.ndarray:
        """
        Devuelve una máscara binaria con las zonas probables de velas.
        """

        hsv = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2HSV,
        )

        white_mask = self._build_white_mask(
            hsv=hsv,
        )
        red_mask = self._build_red_mask(
            hsv=hsv,
        )

        mask = cv2.bitwise_or(
            white_mask,
            red_mask,
        )

        return self._clean_mask(
            mask=mask,
        )

    def _build_white_mask(
        self,
        hsv: np.ndarray,
    ) -> np.ndarray:

        lower = np.array(
            [
                0,
                0,
                self._white_min_value,
            ],
            dtype=np.uint8,
        )
        upper = np.array(
            [
                180,
                self._white_max_saturation,
                255,
            ],
            dtype=np.uint8,
        )

        return cv2.inRange(
            hsv,
            lower,
            upper,
        )

    def _build_red_mask(
        self,
        hsv: np.ndarray,
    ) -> np.ndarray:

        lower_red_1 = np.array(
            [
                0,
                self._red_min_saturation,
                self._red_min_value,
            ],
            dtype=np.uint8,
        )
        upper_red_1 = np.array(
            [
                15,
                255,
                255,
            ],
            dtype=np.uint8,
        )

        lower_red_2 = np.array(
            [
                165,
                self._red_min_saturation,
                self._red_min_value,
            ],
            dtype=np.uint8,
        )
        upper_red_2 = np.array(
            [
                180,
                255,
                255,
            ],
            dtype=np.uint8,
        )

        red_mask_1 = cv2.inRange(
            hsv,
            lower_red_1,
            upper_red_1,
        )
        red_mask_2 = cv2.inRange(
            hsv,
            lower_red_2,
            upper_red_2,
        )

        return cv2.bitwise_or(
            red_mask_1,
            red_mask_2,
        )

    def _clean_mask(
        self,
        mask: np.ndarray,
    ) -> np.ndarray:
        """
        Conserva cuerpos delgados y mechas verticales.

        Un cierre morfológico vertical:
        - mantiene dojis y cuerpos de pocos píxeles;
        - reconecta pequeños espacios entre cuerpo y mecha;
        - evita unir horizontalmente velas vecinas.
        """

        if self._kernel_size <= 1:
            return mask.copy()

        vertical_kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT,
            (
                1,
                self._kernel_size,
            ),
        )

        return cv2.morphologyEx(
            mask,
            cv2.MORPH_CLOSE,
            vertical_kernel,
            iterations=1,
        )
