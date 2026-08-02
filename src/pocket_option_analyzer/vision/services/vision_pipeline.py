from __future__ import annotations

import numpy as np

from pocket_option_analyzer.vision.preprocessing import (
    FrameValidator,
    ImageConverter,
    RegionExtractor,
)


class VisionPipeline:
    """
    Pipeline de preprocesamiento de imágenes.
    """

    def process(
        self,
        image: np.ndarray,
        roi: tuple[int, int, int, int] | None = None,
    ) -> np.ndarray:
        """
        Procesa una imagen para dejarla lista para análisis.
        """

        if not FrameValidator.validate(image):
            raise ValueError("Invalid image.")

        if image.shape[2] == 4:
            image = ImageConverter.bgra_to_bgr(image)

        if roi is not None:
            x, y, width, height = roi

            image = RegionExtractor.extract(
                image=image,
                x=x,
                y=y,
                width=width,
                height=height,
            )

        return image
