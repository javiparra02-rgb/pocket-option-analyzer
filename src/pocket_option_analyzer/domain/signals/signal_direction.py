from __future__ import annotations

from enum import Enum


class SignalDirection(str, Enum):
    """
    Dirección de una señal generada por el sistema.

    El programa solo informa señales.
    Nunca ejecuta operaciones automáticamente.
    """

    CALL = "call"

    PUT = "put"

    NONE = "none"
