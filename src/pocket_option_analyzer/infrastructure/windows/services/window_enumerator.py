from __future__ import annotations

from pocket_option_analyzer.infrastructure.windows.native.user32 import (
    User32,
)


class WindowEnumerator:
    """
    Servicio responsable de enumerar las ventanas del sistema.

    En el siguiente módulo implementaremos la lógica basada en
    EnumWindows.
    """

    def __init__(
        self,
        user32: User32,
    ) -> None:
        self._user32 = user32