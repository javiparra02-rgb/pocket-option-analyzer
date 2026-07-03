from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class WindowInfo:
    """
    Información completa de una ventana de Windows.

    Este modelo es independiente de la tecnología utilizada para
    localizar o capturar la ventana.
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