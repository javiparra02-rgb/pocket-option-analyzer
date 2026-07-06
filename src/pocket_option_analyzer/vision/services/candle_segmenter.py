from __future__ import annotations

import cv2
import numpy as np

from pocket_option_analyzer.vision.models import (
    CandleCandidate,
)


class CandleSegmenter:
    """
    Localiza componentes conectados dentro de una máscara binaria.
    """

    def segment(
        self,
        mask: np.ndarray,
    ) -> list[CandleCandidate]:

        contours, _ = cv2.findContours(
            mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )

        candles: list[CandleCandidate] = []

        for contour in contours:

            x, y, w, h = cv2.boundingRect(contour)

            candles.append(
                CandleCandidate(
                    x=x,
                    y=y,
                    width=w,
                    height=h,
                    area=w * h,
                )
            )

        return candles