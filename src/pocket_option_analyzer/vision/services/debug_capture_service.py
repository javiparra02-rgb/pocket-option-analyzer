from __future__ import annotations

from pathlib import Path

import numpy as np

from pocket_option_analyzer.vision.services.chart_region_extractor import (
    ChartRegion,
)
from pocket_option_analyzer.vision.services.debug_image_saver import (
    DebugImageSaver,
)
from pocket_option_analyzer.vision.services.roi_debug_renderer import (
    RoiDebugRenderer,
)


class DebugCaptureService:
    """
    Genera todas las imágenes de depuración del proceso de captura.
    """

    def __init__(self, output_dir: Path) -> None:
        self._saver = DebugImageSaver(output_dir)
        self._renderer = RoiDebugRenderer()

    def save(
        self,
        image: np.ndarray,
        region: ChartRegion,
    ) -> None:

        # Imagen original
        self._saver.save(
            image,
            "001_window.png",
        )

        # Overlay
        overlay = self._renderer.render(
            image,
            region,
        )

        self._saver.save(
            overlay,
            "002_roi_overlay.png",
        )

        # Recorte ROI

        roi = image[
            region.top : region.top + region.height,
            region.left : region.left + region.width,
        ]

        self._saver.save(
            roi,
            "003_chart_roi.png",
        )
