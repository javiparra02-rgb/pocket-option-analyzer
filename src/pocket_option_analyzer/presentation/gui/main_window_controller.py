from __future__ import annotations

from pocket_option_analyzer.application.runtime import (
    AnalysisRuntimeService,
)
from pocket_option_analyzer.domain.signals import SignalRecord
from pocket_option_analyzer.presentation.gui.main_window import MainWindow
from pocket_option_analyzer.presentation.signals import (
    SignalRecordPresenter,
)


class MainWindowController:
    """
    Controlador de la ventana principal.

    Conecta:
    - MainWindow
    - AnalysisRuntimeService
    - SignalRecordPresenter

    No analiza mercado directamente.
    No captura pantalla directamente.
    No interactúa con Pocket Option.
    Solo coordina acciones de la GUI con el runtime de aplicación.
    """

    def __init__(
        self,
        runtime_service: AnalysisRuntimeService,
        presenter: SignalRecordPresenter | None = None,
        window: MainWindow | None = None,
    ) -> None:
        self._runtime_service = runtime_service
        self._presenter = presenter or SignalRecordPresenter()

        self._window = window or MainWindow(
            on_start_requested=self.start,
            on_stop_requested=self.stop,
            on_run_once_requested=self.run_once,
        )

        self._window.set_running_state(
            is_running=self._runtime_service.is_running,
        )

    @property
    def window(self) -> MainWindow:
        return self._window

    def start(
        self,
    ) -> None:
        """
        Inicia el runtime y actualiza el estado visual.

        Este método todavía es síncrono.
        Más adelante lo moveremos a un worker/thread para uso continuo.
        """

        self._runtime_service.start()
        self._window.set_running_state(
            is_running=self._runtime_service.is_running,
        )

    def stop(
        self,
    ) -> None:
        """
        Detiene el runtime y actualiza el estado visual.
        """

        self._runtime_service.stop()
        self._window.set_running_state(
            is_running=self._runtime_service.is_running,
        )

    def run_once(
        self,
    ) -> SignalRecord | None:
        """
        Ejecuta un análisis único y muestra la señal si existe.
        """

        record = self._runtime_service.run_once()

        if record is None:
            return None

        view_model = self._presenter.present(
            record=record,
        )

        self._window.update_signal(
            view_model=view_model,
        )

        self._window.set_running_state(
            is_running=self._runtime_service.is_running,
        )

        return record