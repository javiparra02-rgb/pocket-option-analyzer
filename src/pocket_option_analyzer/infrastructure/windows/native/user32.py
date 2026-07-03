from __future__ import annotations

import ctypes


class User32:
    """
    Encapsula el acceso a user32.dll.

    Esta clase centraliza todas las llamadas a la API Win32 para
    facilitar el mantenimiento y las pruebas.
    """

    def __init__(self) -> None:
        self._dll = ctypes.windll.user32

    @property
    def dll(self):
        return self._dll