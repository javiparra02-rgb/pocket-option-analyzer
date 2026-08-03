from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile

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

    Las imágenes se codifican primero en un archivo temporal dentro del
    mismo directorio. La ruta definitiva solo aparece cuando la escritura
    se completó correctamente.
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

        Raises
        ------
        FileExistsError
            Cuando el nombre generado ya está ocupado.
        RuntimeError
            Cuando OpenCV no puede codificar la imagen.
        """

        filename = self._filename_generator.generate()
        destination = self._directory_manager.raw / filename

        if destination.exists():
            raise FileExistsError(f"Dataset image already exists: {destination}")

        temporary_path = self._create_temporary_path(
            destination=destination,
        )

        try:
            write_succeeded = cv2.imwrite(
                str(temporary_path),
                image,
            )

            if not write_succeeded or temporary_path.stat().st_size == 0:
                raise RuntimeError(f"Could not save dataset image: {destination}")

            temporary_path.replace(
                destination,
            )
        except Exception:
            temporary_path.unlink(
                missing_ok=True,
            )
            raise

        return destination

    def _create_temporary_path(
        self,
        destination: Path,
    ) -> Path:
        """
        Reserva un archivo temporal en el mismo directorio.

        Mantenerlo en el mismo directorio permite promocionarlo a la
        ruta definitiva mediante una operación de reemplazo local.
        """

        with NamedTemporaryFile(
            mode="wb",
            prefix=f".{destination.stem}_",
            suffix=destination.suffix,
            dir=self._directory_manager.raw,
            delete=False,
        ) as temporary_file:
            return Path(
                temporary_file.name,
            )
