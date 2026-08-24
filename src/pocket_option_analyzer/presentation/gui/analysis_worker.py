from __future__ import annotations

from collections.abc import Callable
from threading import Event

from PySide6.QtCore import QObject, Signal

from pocket_option_analyzer.application.runtime import (
    AnalysisRuntimeService,
)

IterationGuard = Callable[
    [],
    str | None,
]


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
        sleep_function: Callable[[float], None] | None = None,
        iteration_guard: IterationGuard | None = None,
    ) -> None:
        super().__init__()

        if interval_seconds < 0:
            raise ValueError("Worker interval seconds cannot be negative.")

        self._runtime_service = runtime_service
        self._interval_seconds = interval_seconds
        self._sleep_function = sleep_function
        self._iteration_guard = iteration_guard

        self._is_running = False
        self._stop_event = Event()

    @property
    def is_running(
        self,
    ) -> bool:
        return self._is_running

    def run(
        self,
        max_iterations: int | None = None,
    ) -> None:
        """
        Ejecuta el ciclo de análisis.

        max_iterations se usa principalmente para pruebas.
        En la GUI real se dejará como None y se detendrá con stop().

        Una solicitud de detención realizada antes de iniciar el método
        también se conserva y evita ejecutar capturas.
        """

        if max_iterations is not None and max_iterations <= 0:
            return

        if self._stop_event.is_set():
            self.finished.emit()
            return

        self._is_running = True
        self.running_changed.emit(
            True,
        )

        iterations = 0
        owns_session = False

        try:
            try:
                owns_session = self._runtime_service.start_session()
            except Exception as error:
                self.error_occurred.emit(str(error))
                return
            while not self._stop_event.is_set():
                try:
                    guard_error = self._validate_iteration()

                    if guard_error is not None:
                        self.error_occurred.emit(
                            guard_error,
                        )
                        break

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

                if max_iterations is not None and iterations >= max_iterations:
                    break

                if self._wait_for_next_iteration():
                    break
        finally:
            if owns_session:
                try:
                    self._runtime_service.stop_session()
                except Exception as error:
                    self.error_occurred.emit(str(error))
            self._is_running = False

            self.running_changed.emit(
                False,
            )

            self.finished.emit()

    def _wait_for_next_iteration(
        self,
    ) -> bool:
        """
        Espera hasta el siguiente ciclo.

        En producción usa Event.wait(), que puede ser interrumpido
        inmediatamente por stop().

        sleep_function se conserva únicamente para pruebas deterministas
        y adaptadores existentes.
        """

        if self._sleep_function is None:
            return self._stop_event.wait(
                timeout=self._interval_seconds,
            )

        self._sleep_function(
            self._interval_seconds,
        )

        return self._stop_event.is_set()

    def _validate_iteration(
        self,
    ) -> str | None:
        """
        Ejecuta la validación previa a una captura.

        None indica que la captura puede continuar.
        """

        if self._iteration_guard is None:
            return None

        try:
            return self._iteration_guard()
        except Exception as error:
            return f"Falló la validación previa a la captura: {error}"

    def stop(
        self,
    ) -> None:
        """
        Solicita detener el worker y despierta cualquier espera activa.
        """

        self._stop_event.set()
