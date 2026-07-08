from __future__ import annotations

import sys
from collections.abc import Sequence

from PySide6.QtWidgets import QApplication

from pocket_option_analyzer.presentation.gui.main_window_controller import (
    MainWindowController,
)


class GuiApplication:
    """
    Ejecuta la aplicación gráfica PySide6.

    No analiza mercado directamente.
    No captura pantalla directamente.
    No interactúa con Pocket Option.
    Solo inicializa QApplication, muestra la ventana y ejecuta el loop Qt.
    """

    def __init__(
        self,
        controller: MainWindowController,
        argv: Sequence[str] | None = None,
    ) -> None:
        self._controller = controller
        self._argv = list(
            argv
            if argv is not None
            else sys.argv
        )

    def run(self) -> int:
        """
        Muestra la ventana principal y ejecuta el loop de Qt.
        """

        app = QApplication.instance()

        if app is None:
            app = QApplication(
                self._argv,
            )

        self._controller.window.show()

        return app.exec()