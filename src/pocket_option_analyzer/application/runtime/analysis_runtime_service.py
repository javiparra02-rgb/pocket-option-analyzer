from __future__ import annotations

from typing import Protocol, runtime_checkable

from pocket_option_analyzer.domain.signals import SignalRecord


@runtime_checkable
class FrameAnalysisLoop(Protocol):
    """
    Contrato mínimo que necesita el runtime de aplicación.

    Esto permite que la GUI controle el motor sin depender directamente
    de una implementación concreta.
    """

    @property
    def is_running(self) -> bool:
        """
        Indica si el loop de análisis está activo.
        """

    def run_once(self) -> SignalRecord | None:
        """
        Ejecuta un ciclo único de captura/análisis.
        """

    def start(
        self,
        max_iterations: int | None = None,
    ) -> None:
        """
        Inicia el loop de análisis.
        """

    def stop(self) -> None:
        """
        Solicita detener el loop.
        """


class AnalysisRuntimeService:
    """
    Servicio de aplicación para controlar el motor de análisis.

    Expone una API simple para la futura GUI:
    - iniciar
    - detener
    - ejecutar un ciclo
    - consultar estado

    No ejecuta operaciones.
    No hace clic.
    No interactúa con Pocket Option.
    Solo controla el ciclo de análisis visual.
    """

    def __init__(
        self,
        loop_service: FrameAnalysisLoop,
    ) -> None:
        self._loop_service = loop_service

    @property
    def is_running(self) -> bool:
        return self._loop_service.is_running

    def run_once(self) -> SignalRecord | None:
        """
        Ejecuta una única iteración del análisis.
        """

        return self._loop_service.run_once()

    def start(
        self,
        max_iterations: int | None = None,
    ) -> None:
        """
        Inicia el análisis continuo.

        max_iterations se mantiene para pruebas o depuración.
        """

        self._loop_service.start(
            max_iterations=max_iterations,
        )

    def stop(self) -> None:
        """
        Detiene el análisis continuo.
        """

        self._loop_service.stop()
