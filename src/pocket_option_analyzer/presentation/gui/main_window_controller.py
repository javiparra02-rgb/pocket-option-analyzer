from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from PySide6.QtCore import QThread

from pocket_option_analyzer.application.runtime import (
    AnalysisRuntimeService,
)
from pocket_option_analyzer.domain.signals import SignalRecord
from pocket_option_analyzer.presentation.gui.analysis_worker import (
    AnalysisWorker,
)
from pocket_option_analyzer.presentation.gui.main_window import MainWindow
from pocket_option_analyzer.presentation.signals import (
    SignalRecordPresenter,
)


class WorkerLike(Protocol):
    """
    Contrato mínimo para workers usados por el controlador.
    """

    record_ready: object

    error_occurred: object

    running_changed: object

    finished: object

    @property
    def is_running(self) -> bool:
        """
        Indica si el worker está ejecutándose.
        """

    def run(self) -> None:
        """
        Ejecuta el worker.
        """

    def stop(self) -> None:
        """
        Solicita detener el worker.
        """

    def moveToThread(
        self,
        thread,
    ) -> None:
        """
        Mueve el worker a un QThread.
        """


class ThreadLike(Protocol):
    """
    Contrato mínimo para el thread usado por el controlador.
    """

    started: object

    finished: object

    def start(self) -> None:
        """
        Inicia el thread.
        """

    def quit(self) -> None:
        """
        Solicita detener el thread.
        """


WorkerFactory = Callable[[AnalysisRuntimeService], WorkerLike]

ThreadFactory = Callable[[], ThreadLike]


class MainWindowController:
    """
    Controlador de la ventana principal.

    Conecta:
    - MainWindow
    - AnalysisRuntimeService
    - SignalRecordPresenter
    - AnalysisWorker
    - QThread

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
        worker_factory: WorkerFactory | None = None,
        thread_factory: ThreadFactory | None = None,
        worker_interval_seconds: float = 1.0,
    ) -> None:
        self._runtime_service = runtime_service
        self._presenter = presenter or SignalRecordPresenter()
        self._worker_interval_seconds = worker_interval_seconds

        self._worker_factory = worker_factory or self._create_worker
        self._thread_factory = thread_factory or QThread

        self._worker: WorkerLike | None = None
        self._thread: ThreadLike | None = None

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
        Inicia el análisis continuo en un worker/thread.

        Esto evita bloquear la GUI.
        """

        if self._worker is not None and self._worker.is_running:
            return

        worker = self._worker_factory(
            self._runtime_service,
        )
        thread = self._thread_factory()

        self._worker = worker
        self._thread = thread

        worker.moveToThread(
            thread,
        )

        thread.started.connect(
            worker.run,
        )
        worker.record_ready.connect(
            self._handle_record_ready,
        )
        worker.error_occurred.connect(
            self._handle_error_occurred,
        )
        worker.running_changed.connect(
            self._window.set_running_state,
        )
        worker.finished.connect(
            thread.quit,
        )
        worker.finished.connect(
            self._handle_worker_finished,
        )
        thread.finished.connect(
            self._handle_thread_finished,
        )

        if hasattr(
            worker,
            "deleteLater",
        ):
            worker.finished.connect(
                worker.deleteLater,
            )

        if hasattr(
            thread,
            "deleteLater",
        ):
            thread.finished.connect(
                thread.deleteLater,
            )

        thread.start()

    def stop(
        self,
    ) -> None:
        """
        Solicita detener el análisis continuo.
        """

        if self._worker is not None:
            self._worker.stop()

        self._window.set_running_state(
            is_running=False,
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

        self._handle_record_ready(
            record=record,
        )

        self._window.set_running_state(
            is_running=self._runtime_service.is_running,
        )

        return record

    def _create_worker(
        self,
        runtime_service: AnalysisRuntimeService,
    ) -> AnalysisWorker:

        return AnalysisWorker(
            runtime_service=runtime_service,
            interval_seconds=self._worker_interval_seconds,
        )

    def _handle_record_ready(
        self,
        record: SignalRecord,
    ) -> None:

        view_model = self._presenter.present(
            record=record,
        )

        self._window.update_signal(
            view_model=view_model,
        )

    def _handle_error_occurred(
        self,
        message: str,
    ) -> None:

        self._window.set_running_state(
            is_running=False,
        )

    def _handle_worker_finished(
        self,
    ) -> None:

        self._window.set_running_state(
            is_running=False,
        )

    def _handle_thread_finished(
        self,
    ) -> None:

        self._worker = None
        self._thread = None