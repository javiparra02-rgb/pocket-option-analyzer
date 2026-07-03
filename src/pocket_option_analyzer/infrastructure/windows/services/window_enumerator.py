from __future__ import annotations

import ctypes

from pocket_option_analyzer.infrastructure.windows.native.callbacks import (
    EnumWindowsProc,
)
from pocket_option_analyzer.infrastructure.windows.native.user32 import (
    User32,
)


class WindowEnumerator:
    """
    Enumera los HWND existentes en el sistema.
    """

    def __init__(
        self,
        user32: User32,
    ) -> None:
        self._user32 = user32

    def enumerate_hwnds(self) -> list[int]:
        """
        Devuelve una lista de HWND.
        """

        hwnds: list[int] = []

        @EnumWindowsProc
        def callback(hwnd, lparam):
            del lparam

            hwnds.append(int(ctypes.cast(hwnd, ctypes.c_void_p).value))

            return True

        self._user32.enum_windows(callback)

        return hwnds