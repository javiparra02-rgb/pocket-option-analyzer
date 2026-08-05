from __future__ import annotations

import cv2
import numpy as np

from pocket_option_analyzer.vision.models import ChartRegion


class RoiDebugRenderer:
    """
    Dibuja el ROI del gráfico sobre la captura completa.
    """

    def render(
        self,
        image: np.ndarray,
        region: ChartRegion,
    ) -> np.ndarray:
        """
        Devuelve una copia de la imagen con el rectángulo del ROI.
        """

        output = image.copy()

        cv2.rectangle(
            output,
            (
                region.x,
                region.y,
            ),
            (
                region.right - 1,
                region.bottom - 1,
            ),
            (
                0,
                255,
                0,
            ),
            2,
        )

        label_y = max(
            0,
            region.y - 8,
        )

        cv2.putText(
            output,
            "Chart ROI",
            (
                region.x + 8,
                label_y,
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (
                0,
                255,
                0,
            ),
            2,
            cv2.LINE_AA,
        )

        return output
