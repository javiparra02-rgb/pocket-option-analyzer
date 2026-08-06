from __future__ import annotations

import ctypes
from typing import Any

from .structures import POINT, RECT


class User32:
    """
    Wrapper de user32.dll.

    Centraliza las llamadas Win32 utilizadas por el proyecto y valida
    los códigos de retorno de las operaciones que pueden fallar.
    """

    def __init__(
        self,
        dll: Any | None = None,
    ) -> None:
        self._dll = dll if dll is not None else ctypes.windll.user32

    # =========================================================
    # ENUM WINDOWS
    # =========================================================

    def enum_windows(
        self,
        callback: Any,
    ) -> None:
        """
        Enumera las ventanas de nivel superior disponibles.

        Raises
        ------
        OSError
            Cuando Win32 no puede completar la enumeración.
        """

        succeeded = self._dll.EnumWindows(
            callback,
            0,
        )

        if not succeeded:
            raise OSError("EnumWindows failed.")

    # =========================================================
    # WINDOW VALIDATION
    # =========================================================

    def is_window(
        self,
        hwnd: int,
    ) -> bool:
        """
        Indica si el HWND todavía identifica una ventana válida.
        """

        return bool(
            self._dll.IsWindow(
                hwnd,
            )
        )

    # =========================================================
    # WINDOW TEXT
    # =========================================================

    def get_window_text_length(
        self,
        hwnd: int,
    ) -> int:
        return int(
            self._dll.GetWindowTextLengthW(
                hwnd,
            )
        )

    def get_window_text(
        self,
        hwnd: int,
    ) -> str:
        """
        Lee el título actual de una ventana.

        Un título legítimamente vacío devuelve una cadena vacía. Cuando
        Win32 reporta previamente una longitud positiva pero la copia
        falla, se considera una falla de la API.
        """

        length = self.get_window_text_length(
            hwnd,
        )

        if length <= 0:
            return ""

        buffer = ctypes.create_unicode_buffer(
            length + 1,
        )

        copied_length = self._dll.GetWindowTextW(
            hwnd,
            buffer,
            len(buffer),
        )

        if copied_length <= 0:
            raise OSError(f"GetWindowTextW failed for hwnd={hwnd}.")

        return buffer.value

    # =========================================================
    # WINDOW RECTANGLE
    # =========================================================

    def get_window_rect(
        self,
        hwnd: int,
    ) -> RECT:
        rect = RECT()

        succeeded = self._dll.GetWindowRect(
            hwnd,
            ctypes.byref(
                rect,
            ),
        )

        if not succeeded:
            raise OSError(f"GetWindowRect failed for hwnd={hwnd}.")

        return rect

    def get_client_rect(
        self,
        hwnd: int,
    ) -> RECT:
        rect = RECT()

        succeeded = self._dll.GetClientRect(
            hwnd,
            ctypes.byref(
                rect,
            ),
        )

        if not succeeded:
            raise OSError(f"GetClientRect failed for hwnd={hwnd}.")

        return rect

    # =========================================================
    # COORDINATES
    # =========================================================

    def client_to_screen(
        self,
        hwnd: int,
        point: POINT,
    ) -> POINT:
        """
        Convierte un punto de coordenadas cliente a coordenadas pantalla.
        """

        succeeded = self._dll.ClientToScreen(
            hwnd,
            ctypes.byref(
                point,
            ),
        )

        if not succeeded:
            raise OSError(f"ClientToScreen failed for hwnd={hwnd}.")

        return point

    # =========================================================
    # STATE
    # =========================================================

    def is_window_visible(
        self,
        hwnd: int,
    ) -> bool:
        return bool(
            self._dll.IsWindowVisible(
                hwnd,
            )
        )

    def is_iconic(
        self,
        hwnd: int,
    ) -> bool:
        return bool(
            self._dll.IsIconic(
                hwnd,
            )
        )
