from __future__ import annotations

import time
from collections.abc import Callable
from typing import Protocol

from pocket_option_analyzer.application.use_cases.analyze_captured_frame_use_case import (
    AnalyzeCapturedFrameUseCase,
    FrameLike,
)
from pocket_option_analyzer.domain.signals import SignalRecord


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
    - captura de frame
    - análisis visual
    - registro de señal
    """

    def __init__(
        self,
        capture_service: FrameCaptureService,
        analysis_use_case: AnalyzeCapturedFrameUseCase,
        interval_seconds: float = 1.0,
        sleep_function: Callable[[float], None] = time.sleep,
    ) -> None:
        if interval_seconds < 0:
            raise ValueError("Loop interval seconds cannot be negative.")

        self._capture_service = capture_service
        self._analysis_use_case = analysis_use_case
        self._interval_seconds = interval_seconds
        self._sleep_function = sleep_function
        self._is_running = False

    @property
    def is_running(
        self,
    ) -> bool:
        return self._is_running

    def run_once(
        self,
    ) -> SignalRecord | None:
        """
        Ejecuta un solo ciclo:
        - captura
        - análisis
        - registro

        Devuelve None si no hubo frame disponible.
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
        En producción puede quedar como None.
        """

        if max_iterations is not None and max_iterations <= 0:
            return

        self._is_running = True
        iterations = 0

        try:
            while self._is_running:
                self.run_once()

                iterations += 1

                if max_iterations is not None and iterations >= max_iterations:
                    break

                self._sleep_function(
                    self._interval_seconds,
                )
        finally:
            self._is_running = False

    def stop(
        self,
    ) -> None:
        """
        Solicita detener el ciclo.
        """

        self._is_running = False
