from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


class DebugImageSaver:
    """
    Guarda imágenes del pipeline para depuración.
    """

    def __init__(self, output_dir: Path | str = "debug") -> None:
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        image: np.ndarray,
        filename: str,
    ) -> Path:
        """
        Guarda una imagen y devuelve la ruta generada.
        """
        path = self._output_dir / filename

        if not cv2.imwrite(str(path), image):
            raise RuntimeError(f"No se pudo guardar la imagen: {path}")

        return path