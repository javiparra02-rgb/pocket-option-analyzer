from __future__ import annotations

import cv2
import numpy as np

from pocket_option_analyzer.vision.models.candle_candidate import (
    CandleCandidate,
)
from pocket_option_analyzer.vision.models.candle_color import CandleColor


class CandleColorDetector:
    """
    Detecta el color dominante dentro del área de una vela candidata.

    Trabaja sobre imágenes BGR, que es el formato estándar utilizado
    por OpenCV.
    """

    def __init__(
        self,
        min_pixels: int = 5,
    ) -> None:
        self._min_pixels = min_pixels

    def detect(
        self,
        image: np.ndarray,
        candle: CandleCandidate,
    ) -> CandleColor:
        """
        Detecta si la vela candidata es blanca, roja, verde o desconocida.
        """

        roi = self._extract_roi(
            image=image,
            candle=candle,
        )

        if roi.size == 0:
            return CandleColor.UNKNOWN

        hsv = cv2.cvtColor(
            roi,
            cv2.COLOR_BGR2HSV,
        )

        white_pixels = self._count_white_pixels(hsv)
        red_pixels = self._count_red_pixels(hsv)
        green_pixels = self._count_green_pixels(hsv)

        scores = {
            CandleColor.WHITE: white_pixels,
            CandleColor.RED: red_pixels,
            CandleColor.GREEN: green_pixels,
        }

        detected_color, score = max(
            scores.items(),
            key=lambda item: item[1],
        )

        if score < self._min_pixels:
            return CandleColor.UNKNOWN

        return detected_color

    def _extract_roi(
        self,
        image: np.ndarray,
        candle: CandleCandidate,
    ) -> np.ndarray:

        image_height, image_width = image.shape[:2]

        x1 = max(candle.x, 0)
        y1 = max(candle.y, 0)

        x2 = min(candle.x + candle.width, image_width)
        y2 = min(candle.y + candle.height, image_height)

        return image[y1:y2, x1:x2]

    def _count_white_pixels(
        self,
        hsv: np.ndarray,
    ) -> int:

        lower_white = np.array(
            [0, 0, 180],
            dtype=np.uint8,
        )
        upper_white = np.array(
            [180, 60, 255],
            dtype=np.uint8,
        )

        mask = cv2.inRange(
            hsv,
            lower_white,
            upper_white,
        )

        return int(cv2.countNonZero(mask))

    def _count_red_pixels(
        self,
        hsv: np.ndarray,
    ) -> int:

        lower_red_1 = np.array(
            [0, 80, 80],
            dtype=np.uint8,
        )
        upper_red_1 = np.array(
            [15, 255, 255],
            dtype=np.uint8,
        )

        lower_red_2 = np.array(
            [165, 80, 80],
            dtype=np.uint8,
        )
        upper_red_2 = np.array(
            [180, 255, 255],
            dtype=np.uint8,
        )

        mask_1 = cv2.inRange(
            hsv,
            lower_red_1,
            upper_red_1,
        )
        mask_2 = cv2.inRange(
            hsv,
            lower_red_2,
            upper_red_2,
        )

        mask = cv2.bitwise_or(
            mask_1,
            mask_2,
        )

        return int(cv2.countNonZero(mask))

    def _count_green_pixels(
        self,
        hsv: np.ndarray,
    ) -> int:

        lower_green = np.array(
            [35, 80, 80],
            dtype=np.uint8,
        )
        upper_green = np.array(
            [90, 255, 255],
            dtype=np.uint8,
        )

        mask = cv2.inRange(
            hsv,
            lower_green,
            upper_green,
        )

        return int(cv2.countNonZero(mask))