from __future__ import annotations

from abc import ABC
from abc import abstractmethod

from pocket_option_analyzer.infrastructure.capture.models import WindowInfo


class WindowApi(ABC):
    """
    Contrato para interactuar con ventanas del sistema operativo.
    """

    @abstractmethod
    def find_window(self, title: str) -> WindowInfo | None:
        """
        Busca una ventana.
        """

    @abstractmethod
    def enumerate_windows(self) -> list[WindowInfo]:
        """
        Devuelve todas las ventanas visibles.
        """