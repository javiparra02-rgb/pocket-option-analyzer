from __future__ import annotations

from typing import Protocol


class LoggerProtocol(Protocol):
    """
    Contrato para cualquier implementación de logger.
    """

    def debug(self, message: str) -> None: ...

    def info(self, message: str) -> None: ...

    def warning(self, message: str) -> None: ...

    def error(self, message: str) -> None: ...

    def critical(self, message: str) -> None: ...
