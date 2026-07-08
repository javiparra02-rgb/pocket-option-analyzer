from __future__ import annotations

import sys
from collections.abc import Sequence

from PySide6.QtWidgets import QApplication

from pocket_option_analyzer.infrastructure.bootstrap import (
    PocketOptionRuntimeFactory,
)
from pocket_option_analyzer.presentation.gui import (
    GuiApplication,
    MainWindowController,
)


class NoopRuntimeService:
    """
    Runtime temporal para pruebas.

    La aplicación real usa PocketOptionRuntimeFactory.
    """

    @property
    def is_running(self) -> bool:
        return False

    def run_once(self):
        return None

    def start(
        self,
        max_iterations: int | None = None,
    ) -> None:
        return None

    def stop(self) -> None:
        return None


def ensure_qapplication(
    argv: Sequence[str] | None = None,
) -> QApplication:
    """
    Garantiza que QApplication exista antes de crear cualquier QWidget.
    """

    app = QApplication.instance()

    if app is not None:
        return app

    return QApplication(
        list(
            argv
            if argv is not None
            else sys.argv
        )
    )


def build_gui_application(
    argv: Sequence[str] | None = None,
    runtime_service=None,
) -> GuiApplication:
    """
    Construye la aplicación gráfica.

    Si no se entrega runtime_service, construye el runtime real para
    capturar y analizar Pocket Option.
    """

    ensure_qapplication(
        argv=argv,
    )

    resolved_runtime_service = (
        runtime_service
        if runtime_service is not None
        else PocketOptionRuntimeFactory.create_runtime_service()
    )

    controller = MainWindowController(
        runtime_service=resolved_runtime_service,
    )

    return GuiApplication(
        controller=controller,
        argv=argv,
    )


def main(
    argv: Sequence[str] | None = None,
) -> int:
    """
    Punto de entrada principal de la aplicación.
    """

    application = build_gui_application(
        argv=argv,
    )

    return application.run()


if __name__ == "__main__":
    raise SystemExit(
        main(
            argv=sys.argv,
        )
    )