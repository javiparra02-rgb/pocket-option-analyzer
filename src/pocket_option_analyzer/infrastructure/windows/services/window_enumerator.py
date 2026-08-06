from __future__ import annotations

import ctypes

from pocket_option_analyzer.infrastructure.windows.native import (
    EnumWindowsProc,
    User32,
)


class WindowEnumerator:
    """
    Enumera los HWND de las ventanas de nivel superior del sistema.
    """

    def __init__(
        self,
        user32: User32,
    ) -> None:
        self._user32 = user32

    def enumerate_hwnds(
        self,
    ) -> list[int]:
        """
        Devuelve los HWND válidos encontrados durante la enumeración.

        La colección conserva el orden entregado por Win32.
        """

        hwnds: list[int] = []

        @EnumWindowsProc
        def callback(
            hwnd,
            lparam,
        ) -> bool:
            del lparam

            raw_handle = ctypes.cast(
                hwnd,
                ctypes.c_void_p,
            ).value

            if raw_handle is not None and raw_handle > 0:
                hwnds.append(
                    int(
                        raw_handle,
                    )
                )

            return True

        self._user32.enum_windows(
            callback,
        )

        return hwnds
