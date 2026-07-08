from __future__ import annotations

import sys
from collections.abc import Sequence

from pocket_option_analyzer.presentation.gui import (
    GuiApplication,
    MainWindowController,
)


class NoopRuntimeService:
    """
    Runtime temporal para abrir la GUI sin capturar todavía.

    Será reemplazado por el runtime real construido con SignalPipelineFactory
    cuando conectemos CaptureService.
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


def build_gui_application(
    argv: Sequence[str] | None = None,
) -> GuiApplication:
    """
    Construye la aplicación gráfica.

    Por ahora usa NoopRuntimeService para validar el arranque de la GUI.
    """

    controller = MainWindowController(
        runtime_service=NoopRuntimeService(),
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