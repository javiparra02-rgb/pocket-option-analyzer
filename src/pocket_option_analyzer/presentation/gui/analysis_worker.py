from __future__ import annotations

import time
from collections.abc import Callable

from PySide6.QtCore import QObject, Signal

from pocket_option_analyzer.application.runtime import (
    AnalysisRuntimeService,
)


class AnalysisWorker(QObject):
    """
    Worker de análisis para la GUI.

    Permite ejecutar análisis continuo sin poner lógica de mercado
    dentro de la ventana principal.

    No ejecuta operaciones.
    No hace clic.
    No interactúa con Pocket Option.
    Solo invoca el runtime de análisis y emite resultados.
    """

    record_ready = Signal(object)

    error_occurred = Signal(str)

    running_changed = Signal(bool)

    finished = Signal()

    def __init__(
        self,
        runtime_service: AnalysisRuntimeService,
        interval_seconds: float = 1.0,
        sleep_function: Callable[[float], None] = time.sleep,
    ) -> None:
        super().__init__()

        if interval_seconds < 0:
            raise ValueError("Worker interval seconds cannot be negative.")

        self._runtime_service = runtime_service
        self._interval_seconds = interval_seconds
        self._sleep_function = sleep_function
        self._is_running = False
        self._stop_requested = False

    @property
    def is_running(self) -> bool:
        return self._is_running

    def run(
        self,
        max_iterations: int | None = None,
    ) -> None:
        """
        Ejecuta el ciclo de análisis.

        max_iterations se usa principalmente para pruebas.
        En la GUI real se dejará como None y se detendrá con stop().
        """

        if max_iterations is not None and max_iterations <= 0:
            return

        self._stop_requested = False
        self._is_running = True
        self.running_changed.emit(True)

        iterations = 0

        try:
            while not self._stop_requested:
                try:
                    record = self._runtime_service.run_once()
                except Exception as error:
                    self.error_occurred.emit(
                        str(error),
                    )
                    break

                if record is not None:
                    self.record_ready.emit(
                        record,
                    )

                iterations += 1

                if (
                    max_iterations is not None
                    and iterations >= max_iterations
                ):
                    break

                self._sleep_function(
                    self._interval_seconds,
                )
        finally:
            self._is_running = False
            self.running_changed.emit(False)
            self.finished.emit()

    def stop(self) -> None:
        """
        Solicita detener el worker.
        """

        self._stop_requested = True