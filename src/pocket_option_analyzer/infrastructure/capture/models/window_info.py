from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class WindowInfo:
    """
    Información de una ventana.

    Este modelo representa una región rectangular de la pantalla.
    """

    title: str

    left: int
    top: int

    width: int
    height: int

    @property
    def right(self) -> int:
        """
        Coordenada derecha.
        """
        return self.left + self.width

    @property
    def bottom(self) -> int:
        """
        Coordenada inferior.
        """
        return self.top + self.height
