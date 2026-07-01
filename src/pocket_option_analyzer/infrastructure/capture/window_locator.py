from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WindowInfo:
    """
    Información de una ventana localizada.
    """

    title: str
    left: int
    top: int
    width: int
    height: int


class WindowLocator:
    """
    Localizador de la ventana de Pocket Option.

    En esta primera versión solo define el contrato.
    La implementación específica para Windows se añadirá
    mediante un adaptador en el siguiente módulo.
    """

    def find(self, window_title: str) -> WindowInfo:
        """
        Localiza una ventana por su título.

        Raises
        ------
        NotImplementedError
            Hasta que se implemente el adaptador Win32.
        """
        raise NotImplementedError(
            "WindowLocator will be implemented by the Win32 adapter."
        )