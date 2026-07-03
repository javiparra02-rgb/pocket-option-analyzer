from __future__ import annotations

from abc import ABC
from abc import abstractmethod

from pocket_option_analyzer.infrastructure.windows.models.win32_window_info import (
    Win32WindowInfo,
)


class WindowApi(ABC):
    """
    Contrato para interactuar con ventanas del sistema operativo.

    Todas las implementaciones específicas de Windows deberán cumplir
    esta interfaz.
    """

    @abstractmethod
    def find_window(
        self,
        title: str,
    ) -> Win32WindowInfo | None:
        """
        Busca una ventana por su título.
        """

    @abstractmethod
    def enumerate_windows(
        self,
    ) -> list[Win32WindowInfo]:
        """
        Devuelve todas las ventanas disponibles.
        """