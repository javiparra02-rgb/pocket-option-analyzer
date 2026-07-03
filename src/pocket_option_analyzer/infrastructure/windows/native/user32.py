from __future__ import annotations

import ctypes
from typing import Any


class User32:
    """
    Encapsula las llamadas a user32.dll.

    Esta clase será el único punto de acceso a la API User32 de
    Windows dentro del proyecto.
    """

    def __init__(self) -> None:
        self._dll = ctypes.windll.user32

    def enum_windows(self, callback: Any) -> None:
        """
        Ejecuta EnumWindows utilizando el callback proporcionado.
        """
        self._dll.EnumWindows(callback, 0)