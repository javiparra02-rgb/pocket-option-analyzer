from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

import cv2
import numpy as np

RuntimeRoiClock = Callable[[], datetime]
RuntimeRoiTokenFactory = Callable[[], str]
RuntimeRoiImageWriter = Callable[
    [
        str,
        np.ndarray,
    ],
    bool,
]


def _runtime_roi_utc_now() -> datetime:
    """
    Devuelve la fecha y hora actual en UTC.
    """

    return datetime.now(
        tz=UTC,
    )


def _runtime_roi_unique_token() -> str:
    """
    Genera un token único para el nombre de una captura ROI.
    """

    return uuid4().hex


class RuntimeRoiDebugCapture:
    """
    Guarda el ROI real que será analizado por el sistema.

    El directorio mantiene únicamente una cantidad acotada de capturas.
    La imagen definitiva solo aparece después de completar correctamente
    la escritura del archivo temporal.
    """

    DEFAULT_MAX_FILES = 300

    def __init__(
        self,
        directory: Path = Path("debug") / "runtime_roi",
        filename_prefix: str = "roi",
        max_files: int = DEFAULT_MAX_FILES,
        clock: RuntimeRoiClock = _runtime_roi_utc_now,
        token_factory: RuntimeRoiTokenFactory = _runtime_roi_unique_token,
        image_writer: RuntimeRoiImageWriter = cv2.imwrite,
    ) -> None:
        if max_files < 1:
            raise ValueError("Runtime ROI max files must be greater than zero.")

        self._directory = directory
        self._filename_prefix = filename_prefix
        self._max_files = max_files
        self._clock = clock
        self._token_factory = token_factory
        self._image_writer = image_writer

        self._latest_path: Path | None = None

    @property
    def latest_path(
        self,
    ) -> Path | None:
        """
        Devuelve la ruta de la última captura guardada correctamente.
        """

        return self._latest_path

    @property
    def max_files(
        self,
    ) -> int:
        """
        Devuelve el límite máximo de capturas retenidas.
        """

        return self._max_files

    def save(
        self,
        image: np.ndarray,
    ) -> None:
        """
        Guarda el ROI y elimina las capturas más antiguas.

        La escritura utiliza un archivo temporal dentro del mismo
        directorio para evitar publicar imágenes incompletas.
        """

        self._directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        destination = self._directory / self._generate_filename()

        if destination.exists():
            raise FileExistsError(
                f"Runtime ROI debug image already exists: {destination}"
            )

        temporary_path = self._create_temporary_path(
            destination=destination,
        )

        try:
            write_succeeded = self._image_writer(
                str(temporary_path),
                image,
            )

            if not write_succeeded or temporary_path.stat().st_size == 0:
                raise RuntimeError(
                    f"Could not save runtime ROI debug image: {destination}"
                )

            if destination.exists():
                raise FileExistsError(
                    f"Runtime ROI debug image already exists: {destination}"
                )

            temporary_path.replace(
                destination,
            )
        except Exception:
            temporary_path.unlink(
                missing_ok=True,
            )
            raise

        self._latest_path = destination

        self._prune_old_files()

    def _generate_filename(
        self,
    ) -> str:
        captured_at = self._clock()

        if captured_at.tzinfo is None:
            captured_at = captured_at.replace(
                tzinfo=UTC,
            )

        timestamp = captured_at.astimezone(
            UTC,
        ).strftime(
            "%Y%m%d_%H%M%S_%f",
        )

        unique_token = self._token_factory()

        if not unique_token:
            raise ValueError("Runtime ROI filename token cannot be empty.")

        return f"{self._filename_prefix}_{timestamp}_{unique_token}.png"

    def _create_temporary_path(
        self,
        destination: Path,
    ) -> Path:
        """
        Reserva un archivo temporal en el directorio definitivo.
        """

        with NamedTemporaryFile(
            mode="wb",
            prefix=f".{destination.stem}_",
            suffix=destination.suffix,
            dir=self._directory,
            delete=False,
        ) as temporary_file:
            return Path(
                temporary_file.name,
            )

    def _prune_old_files(
        self,
    ) -> None:
        """
        Elimina únicamente capturas antiguas pertenecientes al servicio.
        """

        expected_prefix = f"{self._filename_prefix}_"

        captured_files = [
            path
            for path in self._directory.iterdir()
            if (
                path.is_file()
                and path.name.startswith(
                    expected_prefix,
                )
                and path.suffix.lower() == ".png"
            )
        ]

        captured_files.sort(
            key=lambda path: (
                path == self._latest_path,
                path.name,
            ),
            reverse=True,
        )

        stale_files = captured_files[self._max_files :]

        for stale_path in stale_files:
            stale_path.unlink(
                missing_ok=True,
            )
