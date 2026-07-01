from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from pocket_option_analyzer.infrastructure.config import Settings


class LoggingManager:
    """
    Configura y expone el logger de la aplicación.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._logger = logger

    def configure(self) -> None:
        """
        Configura los destinos y formato del logger.
        """

        self._logger.remove()

        self._logger.add(
            sys.stdout,
            level=self._settings.log_level,
            colorize=True,
            enqueue=True,
            backtrace=True,
            diagnose=False,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                "<level>{level:<8}</level> | "
                "{name}:{function}:{line} | "
                "<level>{message}</level>"
            ),
        )

        log_dir = Path(self._settings.log_directory)
        log_dir.mkdir(parents=True, exist_ok=True)

        self._logger.add(
            log_dir / "application.log",
            rotation="10 MB",
            retention="14 days",
            compression="zip",
            enqueue=True,
            level=self._settings.log_level,
        )

    @property
    def logger(self):
        """
        Devuelve la instancia configurada de Loguru.
        """
        return self._logger