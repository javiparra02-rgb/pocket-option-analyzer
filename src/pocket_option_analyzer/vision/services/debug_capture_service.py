from __future__ import annotations

from pathlib import Path

import numpy as np

from pocket_option_analyzer.vision.models import ChartRegion
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

    def __init__(
        self,
        output_dir: Path,
    ) -> None:
        self._saver = DebugImageSaver(
            output_dir,
        )
        self._renderer = RoiDebugRenderer()

    def save(
        self,
        image: np.ndarray,
        region: ChartRegion,
    ) -> None:
        """
        Guarda la captura completa, el overlay y el ROI independiente.
        """

        self._saver.save(
            image,
            "001_window.png",
        )

        overlay = self._renderer.render(
            image,
            region,
        )

        self._saver.save(
            overlay,
            "002_roi_overlay.png",
        )

        roi = image[
            region.y : region.bottom,
            region.x : region.right,
        ].copy(
            order="C",
        )

        self._saver.save(
            roi,
            "003_chart_roi.png",
        )
