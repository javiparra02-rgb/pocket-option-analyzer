from __future__ import annotations

import ctypes
from typing import Any

from .structures import POINT, RECT


class User32:
    """
    Wrapper de user32.dll.

    Centraliza todas las llamadas a la API User32 utilizadas por el
    proyecto.
    """

    def __init__(self) -> None:
        self._dll = ctypes.windll.user32

    # ---------------------------------------------------------
    # Enumeración
    # ---------------------------------------------------------

    def enum_windows(self, callback: Any) -> None:
        """
        Ejecuta EnumWindows.
        """
        self._dll.EnumWindows(callback, 0)

    # ---------------------------------------------------------
    # Información de ventanas
    # ---------------------------------------------------------

    def get_window_text_length(self, hwnd: int) -> int:
        """
        Devuelve la longitud del título.
        """
        return int(self._dll.GetWindowTextLengthW(hwnd))

    def get_window_text(self, hwnd: int) -> str:
        """
        Devuelve el título de una ventana.
        """
        length = self.get_window_text_length(hwnd)

        buffer = ctypes.create_unicode_buffer(length + 1)

        self._dll.GetWindowTextW(
            hwnd,
            buffer,
            len(buffer),
        )

        return buffer.value

    def get_window_rect(self, hwnd: int) -> RECT:
        """
        Devuelve el rectángulo exterior.
        """
        rect = RECT()

        self._dll.GetWindowRect(
            hwnd,
            ctypes.byref(rect),
        )

        return rect

    def get_client_rect(self, hwnd: int) -> RECT:
        """
        Devuelve el rectángulo cliente.
        """
        rect = RECT()

        self._dll.GetClientRect(
            hwnd,
            ctypes.byref(rect),
        )

        return rect

    def client_to_screen(
        self,
        hwnd: int,
        point: POINT,
    ) -> POINT:
        """
        Convierte coordenadas cliente → pantalla.
        """
        self._dll.ClientToScreen(
            hwnd,
            ctypes.byref(point),
        )

        return point

    # ---------------------------------------------------------
    # Estado
    # ---------------------------------------------------------

    def is_window_visible(self, hwnd: int) -> bool:
        """
        Indica si la ventana es visible.
        """
        return bool(self._dll.IsWindowVisible(hwnd))

    def is_iconic(self, hwnd: int) -> bool:
        """
        Indica si la ventana está minimizada.
        """
        return bool(self._dll.IsIconic(hwnd))