from __future__ import annotations

from pocket_option_analyzer.infrastructure.windows.models import Win32WindowInfo
from pocket_option_analyzer.infrastructure.windows.native import User32
from pocket_option_analyzer.infrastructure.windows.services.window_factory import (
    WindowFactory,
)


class WindowReader:
    """
    Construye un Win32WindowInfo completo a partir de un HWND.
    """

    def __init__(
        self,
        user32: User32,
        factory: WindowFactory,
    ) -> None:
        self._user32 = user32
        self._factory = factory

    def read(self, hwnd: int) -> Win32WindowInfo:
        """
        Lee toda la información de una ventana Win32.
        """

        title = self._user32.get_window_text(hwnd)

        window_rect = self._user32.get_window_rect(hwnd)
        client_rect = self._user32.get_client_rect(hwnd)

        visible = self._user32.is_window_visible(hwnd)
        minimized = self._user32.is_iconic(hwnd)

        # Conversión cliente a pantalla (coordenadas cliente top-left)
        client_point = self._user32.client_to_screen(hwnd, client_rect)

        return self._factory.create(
            hwnd=hwnd,
            title=title,
            left=window_rect.left,
            top=window_rect.top,
            width=window_rect.right - window_rect.left,
            height=window_rect.bottom - window_rect.top,
            client_left=client_point.x,
            client_top=client_point.y,
            client_width=client_rect.right - client_rect.left,
            client_height=client_rect.bottom - client_rect.top,
            visible=visible,
            minimized=minimized,
        )