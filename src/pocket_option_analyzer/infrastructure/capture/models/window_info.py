from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WindowInfo:
    """
    Representa la información de una ventana del sistema.
    """

    title: str
    left: int
    top: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height