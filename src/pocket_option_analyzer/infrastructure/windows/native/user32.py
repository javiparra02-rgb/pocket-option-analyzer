from __future__ import annotations

import ctypes
from typing import Any

from .structures import POINT, RECT


class User32:
    """
    Wrapper de user32.dll.
    Centraliza llamadas Win32 utilizadas por el proyecto.
    """

    def __init__(self) -> None:
        self._dll = ctypes.windll.user32

    # =========================================================
    # ENUM WINDOWS
    # =========================================================

    def enum_windows(self, callback: Any) -> None:
        self._dll.EnumWindows(callback, 0)

    # =========================================================
    # WINDOW TEXT
    # =========================================================

    def get_window_text_length(self, hwnd: int) -> int:
        return int(self._dll.GetWindowTextLengthW(hwnd))

    def get_window_text(self, hwnd: int) -> str:
        length = self.get_window_text_length(hwnd)

        buffer = ctypes.create_unicode_buffer(length + 1)

        self._dll.GetWindowTextW(hwnd, buffer, len(buffer))

        return buffer.value

    # =========================================================
    # WINDOW RECTANGLE
    # =========================================================

    def get_window_rect(self, hwnd: int) -> RECT:
        rect = RECT()
        self._dll.GetWindowRect(hwnd, ctypes.byref(rect))
        return rect

    def get_client_rect(self, hwnd: int) -> RECT:
        rect = RECT()
        self._dll.GetClientRect(hwnd, ctypes.byref(rect))
        return rect

    # =========================================================
    # COORDINATES
    # =========================================================

    def client_to_screen(self, hwnd: int, point: POINT) -> POINT:
        self._dll.ClientToScreen(hwnd, ctypes.byref(point))
        return point

    # =========================================================
    # STATE
    # =========================================================

    def is_window_visible(self, hwnd: int) -> bool:
        return bool(self._dll.IsWindowVisible(hwnd))

    def is_iconic(self, hwnd: int) -> bool:
        return bool(self._dll.IsIconic(hwnd))
