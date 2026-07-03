from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class Win32WindowInfo:
    """
    Representa una ventana nativa de Windows.

    Contiene toda la información obtenida desde la API Win32.
    """

    hwnd: int

    title: str

    left: int
    top: int

    width: int
    height: int

    client_left: int
    client_top: int

    client_width: int
    client_height: int

    visible: bool

    minimized: bool

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height