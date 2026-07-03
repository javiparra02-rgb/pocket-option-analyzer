from __future__ import annotations

import ctypes

from .callbacks import EnumWindowsProc


class User32:
    """
    Encapsula las llamadas a user32.dll.
    """

    def __init__(self) -> None:
        self._dll = ctypes.windll.user32

    def enum_windows(self, callback: EnumWindowsProc) -> None:
        """
        Ejecuta EnumWindows.
        """
        self._dll.EnumWindows(callback, 0)