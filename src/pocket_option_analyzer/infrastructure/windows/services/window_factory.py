from __future__ import annotations

from pocket_option_analyzer.infrastructure.windows.models import (
    Win32WindowInfo,
)


class WindowFactory:
    """
    Construye objetos Win32WindowInfo.

    Esta clase concentra toda la lógica de creación del modelo
    para evitar duplicación en los adaptadores.
    """

    def create(
        self,
        *,
        hwnd: int,
        title: str,
        left: int,
        top: int,
        width: int,
        height: int,
        client_left: int,
        client_top: int,
        client_width: int,
        client_height: int,
        visible: bool,
        minimized: bool,
    ) -> Win32WindowInfo:
        return Win32WindowInfo(
            hwnd=hwnd,
            title=title,
            left=left,
            top=top,
            width=width,
            height=height,
            client_left=client_left,
            client_top=client_top,
            client_width=client_width,
            client_height=client_height,
            visible=visible,
            minimized=minimized,
        )
