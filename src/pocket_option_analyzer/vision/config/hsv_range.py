from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HSVRange:
    """
    Representa un rango HSV.
    """

    lower: tuple[int, int, int]
    upper: tuple[int, int, int]