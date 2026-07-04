from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from pocket_option_analyzer.vision.services.dataset_directory_manager import (
    DatasetDirectoryManager,
)
from pocket_option_analyzer.vision.services.dataset_filename_generator import (
    DatasetFilenameGenerator,
)


class DatasetCaptureService:
    """
    Guarda imágenes del gráfico para construir el dataset del proyecto.
    """

    def __init__(
        self,
        directory_manager: DatasetDirectoryManager,
        filename_generator: DatasetFilenameGenerator,
    ) -> None:
        self._directory_manager = directory_manager
        self._filename_generator = filename_generator

        self._directory_manager.create()

    def save(
        self,
        image: np.ndarray,
    ) -> Path:
        """
        Guarda una imagen dentro del dataset y devuelve la ruta creada.
        """

        filename = self._filename_generator.generate()

        path = self._directory_manager.raw / filename

        cv2.imwrite(
            str(path),
            image,
        )

        return path