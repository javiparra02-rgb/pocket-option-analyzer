from __future__ import annotations

from collections.abc import Callable
from threading import Event, Lock
from typing import Protocol

from pocket_option_analyzer.domain.signals import SignalRecord

from .analyze_captured_frame_use_case import (
    AnalyzeCapturedFrameUseCase,
    FrameLike,
)


class FrameCaptureService(Protocol):
    """
    Contrato mínimo para un servicio capaz de capturar frames.

    Application no depende de la implementación concreta de infrastructure.
    """

    def capture_once(
        self,
    ) -> FrameLike | None:
        """
        Captura un frame.

        Puede devolver None si no fue posible capturar en ese ciclo.
        """


class FrameAnalysisLoopService:
    """
    Servicio de ciclo continuo para capturar, analizar y registrar señales.

    No ejecuta operaciones.
    No hace clic.
    No interactúa con Pocket Option.

    Solo coordina:
    - captura de frame;
    - análisis visual;
    - registro de señal.
    """

    def __init__(
        self,
        capture_service: FrameCaptureService,
        analysis_use_case: AnalyzeCapturedFrameUseCase,
        interval_seconds: float = 1.0,
        sleep_function: Callable[[float], None] | None = None,
    ) -> None:
        if interval_seconds < 0:
            raise ValueError("Loop interval seconds cannot be negative.")

        self._capture_service = capture_service
        self._analysis_use_case = analysis_use_case
        self._interval_seconds = interval_seconds
        self._sleep_function = sleep_function

        self._is_running = False
        self._stop_event = Event()
        self._state_lock = Lock()

    @property
    def is_running(
        self,
    ) -> bool:
        with self._state_lock:
            return self._is_running

    def run_once(
        self,
    ) -> SignalRecord | None:
        """
        Ejecuta un solo ciclo de captura y análisis.

        Devuelve None cuando no existe un frame disponible.
        """

        frame = self._capture_service.capture_once()

        if frame is None:
            return None

        return self._analysis_use_case.execute(
            frame=frame,
        )

    def start(
        self,
        max_iterations: int | None = None,
    ) -> None:
        """
        Inicia el ciclo continuo.

        max_iterations existe principalmente para pruebas y depuración.
        Un segundo inicio es ignorado mientras el ciclo anterior siga activo.
        """

        if max_iterations is not None and max_iterations <= 0:
            return

        if not self._try_start():
            return

        iterations = 0

        try:
            while not self._stop_event.is_set():
                self.run_once()

                iterations += 1

                if max_iterations is not None and iterations >= max_iterations:
                    break

                if self._wait_for_next_iteration():
                    break
        finally:
            with self._state_lock:
                self._is_running = False

    def stop(
        self,
    ) -> None:
        """
        Solicita detener el ciclo y despierta cualquier espera activa.
        """

        self._stop_event.set()

    def _try_start(
        self,
    ) -> bool:
        """
        Reserva de forma atómica la ejecución del ciclo.

        También limpia una detención anterior para permitir reutilizar
        la misma instancia después de que haya finalizado.
        """

        with self._state_lock:
            if self._is_running:
                return False

            self._stop_event.clear()
            self._is_running = True

            return True

    def _wait_for_next_iteration(
        self,
    ) -> bool:
        """
        Espera hasta la siguiente iteración.

        En producción usa Event.wait(), que puede ser interrumpido por stop().
        sleep_function se conserva para pruebas deterministas.
        """

        if self._sleep_function is None:
            return self._stop_event.wait(
                timeout=self._interval_seconds,
            )

        self._sleep_function(
            self._interval_seconds,
        )

        return self._stop_event.is_set()
