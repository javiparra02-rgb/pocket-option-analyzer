from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from loguru import logger

from pocket_option_analyzer.infrastructure.config import Settings


class LoggingManager:
    """
    Configura y expone el logger técnico de la aplicación.

    El archivo application.log:

    - rota al alcanzar log_max_bytes;
    - conserva log_backup_count archivos anteriores;
    - comprime los archivos rotados cuando está configurado;
    - utiliza una cola para no bloquear el flujo principal.
    """

    FILE_NAME = "application.log"

    CONSOLE_FORMAT = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level:<8}</level> | "
        "{name}:{function}:{line} | "
        "<level>{message}</level>"
    )

    FILE_FORMAT = (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
        "{level:<8} | "
        "{name}:{function}:{line} | "
        "{message}"
    )

    def __init__(
        self,
        settings: Settings,
        logger_instance: Any | None = None,
        enable_console: bool = True,
    ) -> None:
        self._settings = settings
        self._logger = logger_instance if logger_instance is not None else logger
        self._enable_console = enable_console
        self._handler_ids: list[int] = []

    @property
    def logger(
        self,
    ) -> Any:
        """
        Devuelve la instancia configurada de Loguru.
        """

        return self._logger

    @property
    def log_file_path(
        self,
    ) -> Path:
        return (
            Path(
                self._settings.log_directory,
            )
            / self.FILE_NAME
        )

    @property
    def handler_ids(
        self,
    ) -> tuple[int, ...]:
        return tuple(
            self._handler_ids,
        )

    def configure(
        self,
    ) -> None:
        """
        Reemplaza los handlers existentes y configura consola y archivo.
        """

        self._logger.remove()
        self._handler_ids.clear()

        if self._enable_console:
            console_handler_id = self._logger.add(
                sys.stdout,
                level=self._settings.log_level,
                colorize=True,
                enqueue=True,
                backtrace=True,
                diagnose=False,
                format=self.CONSOLE_FORMAT,
            )

            self._handler_ids.append(
                console_handler_id,
            )

        self.log_file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        file_handler_id = self._logger.add(
            self.log_file_path,
            level=self._settings.log_level,
            format=self.FILE_FORMAT,
            rotation=self._settings.log_max_bytes,
            retention=self._settings.log_backup_count,
            compression=self._settings.log_compression,
            enqueue=True,
            backtrace=True,
            diagnose=False,
            encoding="utf-8",
            delay=True,
        )

        self._handler_ids.append(
            file_handler_id,
        )

    def shutdown(
        self,
    ) -> None:
        """
        Espera a que los mensajes encolados terminen de escribirse.
        """

        self._logger.complete()
