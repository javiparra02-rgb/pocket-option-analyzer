from __future__ import annotations

from enum import Enum


class SignalStrength(str, Enum):
    """
    Nivel de confianza o fuerza de una señal.
    """

    NONE = "none"

    LOW = "low"

    MEDIUM = "medium"

    HIGH = "high"