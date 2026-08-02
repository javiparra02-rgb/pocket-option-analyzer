from __future__ import annotations

import cv2
import numpy as np

from pocket_option_analyzer.vision.services.chart_region_extractor import (
    ChartRegion,
)


class RoiDebugRenderer:
    """
    Dibuja el ROI del gráfico sobre la captura completa.
    """

    def render(
        self,
        image: np.ndarray,
        region: ChartRegion,
    ) -> np.ndarray:

        output = image.copy()

        cv2.rectangle(
            output,
            (region.left, region.top),
            (
                region.left + region.width,
                region.top + region.height,
            ),
            (0, 255, 0),
            2,
        )

        cv2.putText(
            output,
            "Chart ROI",
            (region.left + 8, region.top - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )

        return output
