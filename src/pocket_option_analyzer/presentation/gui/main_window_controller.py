from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from PySide6.QtCore import QObject, QThread, Slot

from pocket_option_analyzer.application.runtime import (
    AnalysisRuntimeService,
)
from pocket_option_analyzer.application.session_results import (
    ManualSignalResultSessionService,
)
from pocket_option_analyzer.application.signals import (
    SignalGateAuditTracker,
)
from pocket_option_analyzer.domain.session_results import (
    ManualSignalResult,
)
from pocket_option_analyzer.domain.signals import (
    SignalRecord,
    SignalRecordDisposition,
)
from pocket_option_analyzer.presentation.gui.analysis_worker import (
    AnalysisWorker,
)
from pocket_option_analyzer.presentation.gui.main_window import MainWindow
from pocket_option_analyzer.presentation.signals import (
    SessionResult,
    SignalGateAuditPresenter,
    SignalRecordPresenter,
    SignalRecordViewModel,
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


class VoiceNotifierLike(Protocol):
    """
    Contrato mínimo para notificadores de voz utilizados
    por el controlador.
    """

    def notify(
        self,
        view_model: SignalRecordViewModel,
    ) -> None:
        """
        Anuncia verbalmente una señal cuando corresponde.
        """

    def set_enabled(
        self,
        enabled: bool,
    ) -> None:
        """
        Activa o desactiva las notificaciones.
        """

    def test_voice(
        self,
    ) -> None:
        """
        Reproduce el mensaje de prueba.
        """


class WindowCaptureExcluderLike(Protocol):
    """
    Contrato mínimo para excluir la GUI de capturas de pantalla.
    """

    def allow_capture(
        self,
        window_handle: int,
    ) -> bool:
        """
        Permite temporalmente que la ventana aparezca en capturas.
        """

    @property
    def last_error_code(self) -> int | None:
        """
        Código Win32 del último fallo, cuando esté disponible.
        """

    def exclude(
        self,
        window_handle: int,
    ) -> bool:
        """
        Excluye de la captura la ventana indicada.
        """


WorkerFactory = Callable[[AnalysisRuntimeService], WorkerLike]
ThreadFactory = Callable[[], ThreadLike]


class RecordingSafetyStatusLike(Protocol):
    """
    Resultado mínimo de una comprobación de grabación.
    """

    is_safe: bool
    message: str


class RecordingSafetyGuardLike(Protocol):
    """
    Contrato para validar que el analizador no cubra Pocket Option.
    """

    def check(
        self,
        analyzer_window_handle: int,
    ) -> RecordingSafetyStatusLike:
        """
        Comprueba si la ubicación actual es segura.
        """


class MainWindowController(QObject):
    """
    Controlador de la ventana principal.

    Hereda de QObject para que las señales emitidas desde AnalysisWorker
    puedan ser entregadas correctamente al hilo principal de Qt.

    No analiza mercado directamente.
    No captura pantalla directamente.
    No interactúa con Pocket Option.
    Solo coordina acciones de la GUI con el runtime de aplicación.
    """

    def __init__(
        self,
        runtime_service: AnalysisRuntimeService,
        presenter: SignalRecordPresenter | None = None,
        signal_gate_audit_tracker: SignalGateAuditTracker | None = None,
        signal_gate_audit_presenter: SignalGateAuditPresenter | None = None,
        voice_notifier: VoiceNotifierLike | None = None,
        manual_result_session: ManualSignalResultSessionService | None = None,
        window_capture_excluder: WindowCaptureExcluderLike | None = None,
        recording_safety_guard: RecordingSafetyGuardLike | None = None,
        window: MainWindow | None = None,
        worker_factory: WorkerFactory | None = None,
        thread_factory: ThreadFactory | None = None,
        worker_interval_seconds: float = 1.0,
    ) -> None:
        super().__init__()

        self._runtime_service = runtime_service
        self._presenter = presenter or SignalRecordPresenter()
        self._signal_gate_audit_tracker = (
            signal_gate_audit_tracker
            or SignalGateAuditTracker()
        )

        self._signal_gate_audit_presenter = (
            signal_gate_audit_presenter
            or SignalGateAuditPresenter()
        )
        self._voice_notifier = voice_notifier
        self._manual_result_session = manual_result_session
        self._window_capture_excluder = window_capture_excluder
        self._recording_safety_guard = recording_safety_guard
        self._recording_mode_enabled = False
        self._recording_window_handle: int | None = None
        self._evidence_mode_enabled = False
        self._worker_interval_seconds = worker_interval_seconds

        self._worker_factory = worker_factory or self._create_worker
        self._thread_factory = thread_factory or QThread

        self._worker: WorkerLike | None = None
        self._thread: ThreadLike | None = None

        self._window = window or MainWindow(
            on_start_requested=self.start,
            on_stop_requested=self.stop,
            on_run_once_requested=self.run_once,
            on_voice_enabled_changed=self.set_voice_enabled,
            on_test_voice_requested=self.test_voice,
            on_evidence_mode_changed=self.set_evidence_mode,
            on_session_result_registered=self.register_manual_result,
            on_session_result_undone=self.undo_manual_result,
            on_session_reset_requested=self.reset_manual_result_session,
            on_recording_mode_changed=self.set_recording_mode,
            restore_window_preferences=True,
        )

        self._window.set_running_state(
            is_running=self._runtime_service.is_running,
        )

    @property
    def window(self) -> MainWindow:
        return self._window
    
    def set_voice_enabled(
        self,
        enabled: bool,
    ) -> None:
        """
        Activa o desactiva el notificador de voz.
        """

        if self._voice_notifier is None:
            return

        self._voice_notifier.set_enabled(
            enabled,
        )


    def test_voice(
        self,
    ) -> None:
        """
        Solicita al notificador reproducir el mensaje de prueba.
        """

        if self._voice_notifier is None:
            return

        self._voice_notifier.test_voice()

    def start(
        self,
    ) -> None:
        """
        Inicia el análisis continuo en un worker/thread.

        Las señales del worker vuelven al controlador, que vive en el hilo
        principal de Qt, evitando modificar la GUI desde el hilo secundario.
        """

        if self._worker is not None and self._worker.is_running:
            return

        self._window.set_error_message(
            None,
        )

        if self._evidence_mode_enabled:
            self._window.set_error_message(
                "Restaura la protección de captura antes de iniciar el análisis."
            )
            self._window.set_running_state(
                is_running=False,
            )
            return

        if self._recording_mode_enabled:
            recording_error = self._recording_safety_error()

            if recording_error is not None:
                self._window.set_error_message(
                    recording_error,
                )
                self._window.set_running_state(
                    is_running=False,
                )
                return
        else:
            if not self._ensure_window_capture_exclusion():
                self._window.set_running_state(
                    is_running=False,
                )
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
            self._handle_running_changed,
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

        Para evitar que la GUI tape el gráfico, la ventana se oculta
        temporalmente durante la captura manual.
        """

        self._window.set_error_message(
            None,
        )

        self._prepare_window_for_capture()

        try:
            record = self._runtime_service.run_once()
        except Exception as error:
            self._restore_window_after_capture()
            self._handle_error_occurred(
                message=str(error),
            )
            return None

        self._restore_window_after_capture()

        if record is None:
            return None

        self._handle_record_ready(
            record=record,
        )

        self._window.set_running_state(
            is_running=self._runtime_service.is_running,
        )

        return record

    def _ensure_window_capture_exclusion(
        self,
    ) -> bool:
        """
        Protege el análisis continuo contra la propia ventana de la GUI.

        Cuando no existe un adaptador configurado, conserva el
        comportamiento anterior para pruebas e integraciones alternativas.
        """

        if self._window_capture_excluder is None:
            return True

        try:
            window_handle = self._window.native_window_handle

            was_excluded = self._window_capture_excluder.exclude(
                window_handle=window_handle,
            )
        except Exception as error:
            self._window.set_error_message(
                "No fue posible configurar la protección de captura: "
                f"{error}"
            )
            return False

        if was_excluded:
            return True

        error_code = (
            self._window_capture_excluder.last_error_code
        )

        error_suffix = ""

        if error_code not in {
            None,
            0,
        }:
            error_suffix = (
                f" Código Win32: {error_code}."
            )

        self._window.set_error_message(
            "No fue posible excluir la ventana del analizador "
            "de la captura continua."
            f"{error_suffix} "
            "Mueve la ventana fuera del gráfico o utiliza "
            "«Analizar una vez»."
        )

        return False

    def _prepare_window_for_capture(
        self,
    ) -> None:

        hide_for_capture = getattr(
            self._window,
            "hide_for_capture",
            None,
        )

        if callable(
            hide_for_capture,
        ):
            hide_for_capture()

    def _restore_window_after_capture(
        self,
    ) -> None:

        show_after_capture = getattr(
            self._window,
            "show_after_capture",
            None,
        )

        if callable(
            show_after_capture,
        ):
            show_after_capture()

    def _create_worker(
        self,
        runtime_service: AnalysisRuntimeService,
    ) -> AnalysisWorker:

        return AnalysisWorker(
            runtime_service=runtime_service,
            interval_seconds=self._worker_interval_seconds,
            iteration_guard=self._iteration_guard,
        )

    def _iteration_guard(
        self,
    ) -> str | None:
        """
        Valida la ubicación antes de cada captura continua.
        """

        if not self._recording_mode_enabled:
            return None

        return self._recording_safety_error()

    @Slot(object)
    def _handle_record_ready(
        self,
        record: SignalRecord,
    ) -> None:

        view_model = self._presenter.present(
            record=record,
        )

        gate_audit_snapshot = (
            self._signal_gate_audit_tracker.track(
                record=record,
            )
        )

        self._update_gate_audit(
            snapshot=gate_audit_snapshot,
        )

        if record.is_duplicate_suppressed:
            update_diagnostics_only = getattr(
                self._window,
                "update_diagnostics_only",
                None,
            )

            if callable(
                update_diagnostics_only,
            ):
                update_diagnostics_only(
                    view_model,
                )

            return

        was_counted_as_new_signal = (
            self._window.update_signal(
                view_model=view_model,
            )
        )

        if (
            was_counted_as_new_signal
            and self._manual_result_session is not None
        ):
            self._manual_result_session.track_confirmed_signal(
                record=record,
            )

        if self._voice_notifier is None:
            return

        if (
            record.disposition
            is SignalRecordDisposition.ACTIONABLE_ACCEPTED
        ):
            reset_voice_state = getattr(
                self._voice_notifier,
                "reset",
                None,
            )

            if callable(
                reset_voice_state,
            ):
                reset_voice_state()

        self._voice_notifier.notify(
            view_model=view_model,
        )


    def _update_gate_audit(
        self,
        snapshot,
    ) -> None:
        """
        Actualiza la auditoría del gate cuando la ventana la soporta.

        getattr conserva compatibilidad con fakes y adaptadores
        anteriores utilizados por los tests.
        """

        update_gate_audit = getattr(
            self._window,
            "update_gate_audit",
            None,
        )

        if not callable(
            update_gate_audit,
        ):
            return

        gate_view_model = (
            self._signal_gate_audit_presenter.present(
                snapshot=snapshot,
            )
        )

        update_gate_audit(
            gate_view_model,
        )


    @Slot(str)
    def _handle_error_occurred(
        self,
        message: str,
    ) -> None:

        if self._recording_mode_enabled:
            self._restore_recording_protection()

        self._window.set_error_message(
            message,
        )
        self._window.set_running_state(
            is_running=False,
        )

    @Slot(bool)
    def _handle_running_changed(
        self,
        is_running: bool,
    ) -> None:

        self._window.set_running_state(
            is_running=is_running,
        )

    @Slot()
    def _handle_worker_finished(
        self,
    ) -> None:

        self._window.set_running_state(
            is_running=False,
        )

    @Slot()
    def _handle_thread_finished(
        self,
    ) -> None:

        self._worker = None
        self._thread = None

    def register_manual_result(
        self,
        result: SessionResult,
    ) -> bool:
        """
        Persiste WIN o LOSS para la señal confirmada pendiente.
        """

        if self._manual_result_session is None:
            return True

        try:
            persisted_record = self._manual_result_session.register_result(
                result=ManualSignalResult(
                    result.value,
                ),
            )
        except Exception as error:
            self._window.set_error_message(
                "No fue posible guardar el resultado manual: "
                f"{error}"
            )
            return False

        if persisted_record is None:
            self._window.set_error_message(
                "No existe una señal confirmada pendiente de resultado."
            )
            return False

        self._window.set_error_message(
            None,
        )
        return True

    def undo_manual_result(
        self,
    ) -> bool:
        """
        Persiste la reversión del último resultado manual.
        """

        if self._manual_result_session is None:
            return True

        try:
            reversal_record = self._manual_result_session.undo_last_result()
        except Exception as error:
            self._window.set_error_message(
                "No fue posible deshacer el resultado manual: "
                f"{error}"
            )
            return False

        if reversal_record is None:
            return False

        self._window.set_error_message(
            None,
        )
        return True

    def reset_manual_result_session(
        self,
    ) -> None:
        """
        Reinicia la cola temporal sin borrar el archivo JSONL.
        """

        if self._manual_result_session is not None:
            self._manual_result_session.reset()

    def set_recording_mode(
        self,
        enabled: bool,
    ) -> bool:
        """
        Permite grabar la ventana mientras el análisis está activo.

        Solo se habilita cuando el analizador está completamente fuera
        de la ventana visible de Pocket Option.
        """

        if enabled and self._is_continuous_analysis_active():
            self._window.set_error_message(
                "Detén el análisis antes de activar el modo grabación."
            )
            return False

        if enabled and self._evidence_mode_enabled:
            self._window.set_error_message(
                "Restaura la protección del modo evidencia antes "
                "de activar el modo grabación."
            )
            return False

        if enabled:
            window_handle = self._window.native_window_handle

            recording_error = self._recording_safety_error(
                window_handle=window_handle,
            )

            if recording_error is not None:
                self._window.set_error_message(
                    recording_error,
                )
                return False

            if not self._apply_capture_visibility(
                window_handle=window_handle,
                allow_capture=True,
            ):
                return False

            self._recording_mode_enabled = True
            self._recording_window_handle = window_handle
            self._window.set_error_message(
                None,
            )
            return True

        window_handle = (
            self._recording_window_handle
            or self._window.native_window_handle
        )

        if not self._apply_capture_visibility(
            window_handle=window_handle,
            allow_capture=False,
        ):
            return False

        self._recording_mode_enabled = False
        self._recording_window_handle = None
        self._window.set_error_message(
            None,
        )

        return True


    def _recording_safety_error(
        self,
        window_handle: int | None = None,
    ) -> str | None:
        """
        Devuelve None cuando la ubicación es segura.
        """

        if self._recording_safety_guard is None:
            return (
                "No existe un validador de ubicación para "
                "el modo grabación."
            )

        resolved_handle = (
            window_handle
            or self._recording_window_handle
        )

        if resolved_handle is None:
            return (
                "No se pudo resolver la ventana del analizador."
            )

        try:
            status = self._recording_safety_guard.check(
                analyzer_window_handle=resolved_handle,
            )
        except Exception as error:
            return (
                "No fue posible validar la ubicación para grabar: "
                f"{error}"
            )

        if status.is_safe:
            return None

        return status.message


    def _apply_capture_visibility(
        self,
        window_handle: int,
        allow_capture: bool,
    ) -> bool:
        """
        Cambia la afinidad de captura de la ventana.
        """

        if self._window_capture_excluder is None:
            self._window.set_error_message(
                "No existe un adaptador de protección de captura."
            )
            return False

        try:
            if allow_capture:
                was_applied = (
                    self._window_capture_excluder.allow_capture(
                        window_handle=window_handle,
                    )
                )
            else:
                was_applied = (
                    self._window_capture_excluder.exclude(
                        window_handle=window_handle,
                    )
                )
        except Exception as error:
            self._window.set_error_message(
                "No fue posible cambiar la visibilidad de captura: "
                f"{error}"
            )
            return False

        if was_applied:
            return True

        error_code = (
            self._window_capture_excluder.last_error_code
        )

        error_suffix = ""

        if error_code not in {
            None,
            0,
        }:
            error_suffix = (
                f" Código Win32: {error_code}."
            )

        self._window.set_error_message(
            "No fue posible cambiar la visibilidad de captura."
            f"{error_suffix}"
        )

        return False

    def set_evidence_mode(
        self,
        enabled: bool,
    ) -> bool:
        """
        Activa o desactiva el modo de evidencia.

        El modo evidencia solo puede activarse cuando el análisis continuo
        está detenido. Así la ventana visible no contamina los frames.
        """

        if enabled and self._recording_mode_enabled:
            self._window.set_error_message(
                "Sal del modo grabación antes de activar "
                "el modo evidencia."
            )
            return False

        if enabled and self._is_continuous_analysis_active():
            self._window.set_error_message(
                "Detén el análisis antes de activar el modo evidencia."
            )
            return False

        if self._window_capture_excluder is None:
            self._evidence_mode_enabled = enabled
            return True

        try:
            window_handle = self._window.native_window_handle

            if enabled:
                was_applied = (
                    self._window_capture_excluder.allow_capture(
                        window_handle=window_handle,
                    )
                )
            else:
                was_applied = (
                    self._window_capture_excluder.exclude(
                        window_handle=window_handle,
                    )
                )
        except Exception as error:
            self._window.set_error_message(
                "No fue posible cambiar el modo de captura: "
                f"{error}"
            )
            return False

        if not was_applied:
            error_code = (
                self._window_capture_excluder.last_error_code
            )

            error_suffix = ""

            if error_code not in {
                None,
                0,
            }:
                error_suffix = (
                    f" Código Win32: {error_code}."
                )

            self._window.set_error_message(
                "No fue posible cambiar el modo de captura."
                f"{error_suffix}"
            )
            return False

        self._evidence_mode_enabled = enabled
        self._window.set_error_message(
            None,
        )

        return True

    def _is_continuous_analysis_active(
        self,
    ) -> bool:
        if self._worker is not None and self._worker.is_running:
            return True

        return self._runtime_service.is_running

    def _restore_recording_protection(
        self,
    ) -> None:
        """
        Vuelve al modo protegido después de una validación fallida.
        """

        window_handle = (
            self._recording_window_handle
        )

        if (
            window_handle is not None
            and self._window_capture_excluder is not None
        ):
            try:
                self._window_capture_excluder.exclude(
                    window_handle=window_handle,
                )
            except Exception:
                pass

        self._recording_mode_enabled = False
        self._recording_window_handle = None

        update_window_state = getattr(
            self._window,
            "set_recording_mode_enabled",
            None,
        )

        if callable(
            update_window_state,
        ):
            update_window_state(
                False,
            )