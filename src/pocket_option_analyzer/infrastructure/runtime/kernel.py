from __future__ import annotations

from pocket_option_analyzer.infrastructure.logging import LoggingManager

from .context import ApplicationContext
from .state import RuntimeStatus
from .ticker import Ticker


class ApplicationKernel:
    """
    Kernel principal de la aplicación.

    Coordina el ciclo de vida de la aplicación y el bucle principal.
    """

    def __init__(self, context: ApplicationContext) -> None:
        self._context = context
        self._ticker = Ticker(context.settings.target_fps)
        self._logger = context.logger.logger

    @property
    def context(self) -> ApplicationContext:
        return self._context

    def initialize(self) -> None:
        """
        Inicializa el Kernel.
        """
        self._context.logger.configure()

        self._context.runtime_state.status = RuntimeStatus.INITIALIZED

        self._logger.info("Kernel initialized.")

    def run(self) -> None:
        """
        Ejecuta el bucle principal.
        """
        state = self._context.runtime_state

        state.running = True
        state.status = RuntimeStatus.RUNNING

        self._logger.info("Kernel started.")

        while state.running:
            self.update()

            self._ticker.wait_next()

    def update(self) -> None:
        """
        Ejecuta una iteración del Kernel.
        """
        self._context.runtime_state.frame_count += 1

    def stop(self) -> None:
        """
        Solicita la detención del Kernel.
        """
        self._context.runtime_state.running = False
        self._context.runtime_state.status = RuntimeStatus.STOPPING

    def shutdown(self) -> None:
        """
        Finaliza el Kernel.
        """
        self._context.runtime_state.status = RuntimeStatus.STOPPED

        self._logger.info("Kernel stopped.")