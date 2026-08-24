from __future__ import annotations

from collections.abc import Callable
from threading import Event, Lock, RLock
from typing import Protocol
from uuid import uuid4

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
        session_key_factory: Callable[[], str] | None = None,
    ) -> None:
        if interval_seconds < 0:
            raise ValueError("Loop interval seconds cannot be negative.")

        self._capture_service = capture_service
        self._analysis_use_case = analysis_use_case
        self._interval_seconds = interval_seconds
        self._sleep_function = sleep_function
        self._session_key_factory = session_key_factory or (lambda: uuid4().hex)

        self._is_running = False
        self._stop_event = Event()
        self._state_lock = Lock()
        self._session_lock = RLock()
        self._active_session_key: str | None = None

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

        with self._session_lock:
            owns_session = self._active_session_key is None
            if owns_session:
                self._start_session_locked()
            try:
                frame = self._capture_service.capture_once()

                if frame is None:
                    return None

                return self._analysis_use_case.execute(
                    frame=frame,
                )
            finally:
                if owns_session:
                    self._stop_session_locked()

    def start_session(self) -> bool:
        """Start one logical session, returning whether this call owns it."""

        with self._session_lock:
            if self._active_session_key is not None:
                return False
            self._start_session_locked()
            return True

    def stop_session(self) -> None:
        """Stop session state after any in-flight frame has completed."""

        with self._session_lock:
            self._stop_session_locked()

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
        owns_session = False

        try:
            owns_session = self.start_session()
            while not self._stop_event.is_set():
                self.run_once()

                iterations += 1

                if max_iterations is not None and iterations >= max_iterations:
                    break

                if self._wait_for_next_iteration():
                    break
        finally:
            try:
                if owns_session:
                    self.stop_session()
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

    def _start_session_locked(self) -> None:
        session_key = self._session_key_factory()
        if not isinstance(session_key, str) or not session_key:
            raise ValueError("session_key_factory must return a non-empty string.")
        self._analysis_use_case.start_session(session_key=session_key)
        self._active_session_key = session_key

    def _stop_session_locked(self) -> None:
        if self._active_session_key is None:
            return
        try:
            self._analysis_use_case.stop_session()
        finally:
            self._active_session_key = None
