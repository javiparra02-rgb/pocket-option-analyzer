from __future__ import annotations

from datetime import UTC, datetime

from pocket_option_analyzer.domain.session_results import (
    ManualSignalResult,
)
from pocket_option_analyzer.domain.signals import (
    MarketSignal,
    SignalDirection,
    SignalRecord,
    SignalRecordDisposition,
    SignalStrength,
)
from pocket_option_analyzer.presentation.gui import (
    MainWindowController,
)
from pocket_option_analyzer.presentation.signals import (
    SessionResult,
    SignalRecordPresenter,
)


class FakeSignal:
    def __init__(self) -> None:
        self._callbacks = []

    def connect(
        self,
        callback,
    ) -> None:
        self._callbacks.append(callback)

    def emit(
        self,
        *args,
    ) -> None:
        for callback in list(self._callbacks):
            callback(
                *args,
            )


class FakeRuntimeService:
    def __init__(
        self,
        record: SignalRecord | None = None,
        error: Exception | None = None,
        is_running: bool = False,
    ) -> None:
        self._is_running = is_running
        self.record = record
        self.error = error
        self.run_once_calls = 0

    @property
    def is_running(self) -> bool:
        return self._is_running

    def run_once(self) -> SignalRecord | None:
        self.run_once_calls += 1

        if self.error is not None:
            raise self.error

        return self.record


class FakeWorker:
    def __init__(
        self,
        record: SignalRecord | None = None,
        auto_finish: bool = True,
    ) -> None:
        self.record_ready = FakeSignal()
        self.error_occurred = FakeSignal()
        self.running_changed = FakeSignal()
        self.finished = FakeSignal()

        self.record = record
        self.auto_finish = auto_finish
        self.run_calls = 0
        self.stop_calls = 0
        self.delete_later_calls = 0
        self.moved_thread = None
        self._is_running = False

    @property
    def is_running(self) -> bool:
        return self._is_running

    def moveToThread(
        self,
        thread,
    ) -> None:
        self.moved_thread = thread

    def run(self) -> None:
        self.run_calls += 1
        self._is_running = True
        self.running_changed.emit(
            True,
        )

        if self.record is not None:
            self.record_ready.emit(
                self.record,
            )

        if self.auto_finish:
            self._is_running = False
            self.running_changed.emit(
                False,
            )
            self.finished.emit()

    def stop(self) -> None:
        self.stop_calls += 1
        self._is_running = False
        self.running_changed.emit(
            False,
        )
        self.finished.emit()

    def deleteLater(self) -> None:
        self.delete_later_calls += 1


class FakeThread:
    def __init__(self) -> None:
        self.started = FakeSignal()
        self.finished = FakeSignal()
        self.start_calls = 0
        self.quit_calls = 0
        self.delete_later_calls = 0

    def start(self) -> None:
        self.start_calls += 1
        self.started.emit()

    def quit(self) -> None:
        self.quit_calls += 1
        self.finished.emit()

    def deleteLater(self) -> None:
        self.delete_later_calls += 1


class FakeWindow:
    def __init__(
        self,
        accept_signal: bool = True,
    ) -> None:
        self.running_states: list[bool] = []
        self.view_models = []
        self.error_messages: list[str | None] = []
        self.hide_for_capture_calls = 0
        self.show_after_capture_calls = 0
        self.accept_signal = accept_signal
        self.native_window_handle = 98765
        self.recording_mode_states: list[bool] = []
        self.diagnostic_view_models = []
        self.gate_audit_view_models = []

    def set_running_state(
        self,
        is_running: bool,
    ) -> None:
        self.running_states.append(
            is_running,
        )

    def update_signal(
        self,
        view_model,
    ) -> bool:
        self.view_models.append(
            view_model,
        )

        return self.accept_signal and view_model.is_actionable

    def set_error_message(
        self,
        message: str | None,
    ) -> None:
        self.error_messages.append(
            message,
        )

    def hide_for_capture(
        self,
    ) -> None:
        self.hide_for_capture_calls += 1

    def show_after_capture(
        self,
    ) -> None:
        self.show_after_capture_calls += 1

    def set_recording_mode_enabled(
        self,
        enabled: bool,
    ) -> None:
        self.recording_mode_states.append(
            enabled,
        )

    def update_diagnostics_only(
        self,
        view_model,
    ) -> None:
        self.diagnostic_view_models.append(
            view_model,
        )

    def update_gate_audit(
        self,
        view_model,
    ) -> None:
        self.gate_audit_view_models.append(
            view_model,
        )


class FakeVoiceNotifier:
    def __init__(self) -> None:
        self.view_models = []
        self.enabled_changes: list[bool] = []
        self.test_voice_calls = 0
        self.reset_calls = 0

    def notify(
        self,
        view_model,
    ) -> None:
        self.view_models.append(
            view_model,
        )

    def set_enabled(
        self,
        enabled: bool,
    ) -> None:
        self.enabled_changes.append(
            enabled,
        )

    def test_voice(
        self,
    ) -> None:
        self.test_voice_calls += 1

    def reset(
        self,
    ) -> None:
        self.reset_calls += 1


class FakeWindowCaptureExcluder:
    def __init__(
        self,
        result: bool = True,
        error_code: int | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self._last_error_code = error_code
        self.error = error
        self.excluded_handles: list[int] = []
        self.allowed_handles: list[int] = []

    @property
    def last_error_code(self) -> int | None:
        return self._last_error_code

    def exclude(
        self,
        window_handle: int,
    ) -> bool:
        self.excluded_handles.append(
            window_handle,
        )

        if self.error is not None:
            raise self.error

        return self.result

    def allow_capture(
        self,
        window_handle: int,
    ) -> bool:
        self.allowed_handles.append(
            window_handle,
        )

        if self.error is not None:
            raise self.error

        return self.result


class FakeManualResultSession:
    def __init__(
        self,
        error: Exception | None = None,
    ) -> None:
        self.tracked_records = []
        self.registered_results = []
        self.undo_calls = 0
        self.reset_calls = 0
        self.error = error

    def track_confirmed_signal(
        self,
        record,
    ) -> bool:
        self.tracked_records.append(
            record,
        )
        return True

    def register_result(
        self,
        result,
    ):
        if self.error is not None:
            raise self.error

        self.registered_results.append(
            result,
        )
        return object()

    def undo_last_result(self):
        if self.error is not None:
            raise self.error

        self.undo_calls += 1
        return object()

    def reset(self) -> None:
        self.reset_calls += 1


class FakeRecordingSafetyStatus:
    def __init__(
        self,
        is_safe: bool,
        message: str,
    ) -> None:
        self.is_safe = is_safe
        self.message = message


class FakeRecordingSafetyGuard:
    def __init__(
        self,
        is_safe: bool = True,
        message: str = "Ubicación segura para grabación.",
    ) -> None:
        self.is_safe = is_safe
        self.message = message
        self.received_handles: list[int] = []

    def check(
        self,
        analyzer_window_handle: int,
    ) -> FakeRecordingSafetyStatus:
        self.received_handles.append(
            analyzer_window_handle,
        )

        return FakeRecordingSafetyStatus(
            is_safe=self.is_safe,
            message=self.message,
        )


def _record() -> SignalRecord:

    return SignalRecord(
        signal=MarketSignal(
            direction=SignalDirection.CALL,
            strength=SignalStrength.HIGH,
            reason="Strategy conditions confirmed.",
        ),
        created_at=datetime(
            2026,
            1,
            1,
            10,
            30,
            45,
            tzinfo=UTC,
        ),
        source="controller_test",
    )


def test_controller_initializes_window_running_state() -> None:

    runtime = FakeRuntimeService()
    window = FakeWindow()

    MainWindowController(
        runtime_service=runtime,
        presenter=SignalRecordPresenter(),
        window=window,
    )

    assert window.running_states == [
        False,
    ]


def test_controller_run_once_updates_signal_when_record_exists() -> None:

    runtime = FakeRuntimeService(
        record=_record(),
    )
    window = FakeWindow()

    controller = MainWindowController(
        runtime_service=runtime,
        presenter=SignalRecordPresenter(),
        window=window,
    )

    record = controller.run_once()

    assert record is runtime.record
    assert runtime.run_once_calls == 1
    assert len(window.view_models) == 1
    assert window.view_models[0].direction_label == "CALL"
    assert window.view_models[0].strength_label == "ALTA"
    assert window.view_models[0].source == "controller_test"


def test_controller_run_once_does_not_update_signal_when_record_is_missing() -> None:

    runtime = FakeRuntimeService(
        record=None,
    )
    window = FakeWindow()

    controller = MainWindowController(
        runtime_service=runtime,
        presenter=SignalRecordPresenter(),
        window=window,
    )

    record = controller.run_once()

    assert record is None
    assert runtime.run_once_calls == 1
    assert window.view_models == []


def test_controller_start_runs_worker_inside_thread() -> None:

    runtime = FakeRuntimeService()
    window = FakeWindow()
    record = _record()
    worker = FakeWorker(
        record=record,
    )
    thread = FakeThread()

    controller = MainWindowController(
        runtime_service=runtime,
        presenter=SignalRecordPresenter(),
        window=window,
        worker_factory=lambda runtime_service: worker,
        thread_factory=lambda: thread,
    )

    controller.start()

    assert worker.moved_thread is thread
    assert thread.start_calls == 1
    assert worker.run_calls == 1
    assert thread.quit_calls == 1
    assert worker.delete_later_calls == 1
    assert thread.delete_later_calls == 1
    assert len(window.view_models) == 1
    assert window.view_models[0].direction_label == "CALL"
    assert window.running_states[0] is False
    assert True in window.running_states
    assert window.running_states[-1] is False


def test_controller_stop_requests_worker_stop() -> None:

    runtime = FakeRuntimeService()
    window = FakeWindow()
    worker = FakeWorker(
        record=None,
        auto_finish=False,
    )
    thread = FakeThread()

    controller = MainWindowController(
        runtime_service=runtime,
        presenter=SignalRecordPresenter(),
        window=window,
        worker_factory=lambda runtime_service: worker,
        thread_factory=lambda: thread,
    )

    controller.start()
    controller.stop()

    assert worker.run_calls == 1
    assert worker.stop_calls == 1
    assert thread.quit_calls == 1
    assert window.running_states[-1] is False


def test_controller_ignores_start_when_worker_is_already_running() -> None:

    runtime = FakeRuntimeService()
    window = FakeWindow()
    worker = FakeWorker(
        auto_finish=False,
    )
    thread = FakeThread()

    controller = MainWindowController(
        runtime_service=runtime,
        presenter=SignalRecordPresenter(),
        window=window,
        worker_factory=lambda runtime_service: worker,
        thread_factory=lambda: thread,
    )

    controller.start()
    controller.start()

    assert thread.start_calls == 1
    assert worker.run_calls == 1


def test_controller_run_once_displays_error_when_runtime_fails() -> None:

    runtime = FakeRuntimeService(
        error=RuntimeError("capture failed"),
    )
    window = FakeWindow()

    controller = MainWindowController(
        runtime_service=runtime,
        presenter=SignalRecordPresenter(),
        window=window,
    )

    record = controller.run_once()

    assert record is None
    assert runtime.run_once_calls == 1
    assert window.error_messages == [
        None,
        "capture failed",
    ]
    assert window.running_states[-1] is False


def test_controller_run_once_hides_and_restores_window_during_capture() -> None:

    runtime = FakeRuntimeService(
        record=_record(),
    )
    window = FakeWindow()

    controller = MainWindowController(
        runtime_service=runtime,
        presenter=SignalRecordPresenter(),
        window=window,
    )

    record = controller.run_once()

    assert record is runtime.record
    assert window.hide_for_capture_calls == 1
    assert window.show_after_capture_calls == 1
    assert len(window.view_models) == 1


def test_controller_receives_worker_running_state_through_controller_slot() -> None:

    runtime = FakeRuntimeService()
    window = FakeWindow()
    worker = FakeWorker(
        auto_finish=False,
    )
    thread = FakeThread()

    controller = MainWindowController(
        runtime_service=runtime,
        presenter=SignalRecordPresenter(),
        window=window,
        worker_factory=lambda runtime_service: worker,
        thread_factory=lambda: thread,
    )

    controller.start()

    assert window.running_states == [
        False,
        True,
    ]

    worker.running_changed.emit(
        False,
    )

    assert window.running_states[-1] is False


def test_controller_notifies_voice_when_record_is_ready() -> None:

    runtime = FakeRuntimeService(
        record=_record(),
    )
    window = FakeWindow()
    voice_notifier = FakeVoiceNotifier()

    controller = MainWindowController(
        runtime_service=runtime,
        presenter=SignalRecordPresenter(),
        voice_notifier=voice_notifier,
        window=window,
    )

    record = controller.run_once()

    assert record is runtime.record
    assert len(window.view_models) == 1
    assert len(voice_notifier.view_models) == 1
    assert voice_notifier.view_models[0] is window.view_models[0]
    assert voice_notifier.view_models[0].direction_label == "CALL"
    assert voice_notifier.view_models[0].is_actionable is True


def test_controller_does_not_notify_voice_when_record_is_missing() -> None:

    runtime = FakeRuntimeService(
        record=None,
    )
    window = FakeWindow()
    voice_notifier = FakeVoiceNotifier()

    controller = MainWindowController(
        runtime_service=runtime,
        presenter=SignalRecordPresenter(),
        voice_notifier=voice_notifier,
        window=window,
    )

    record = controller.run_once()

    assert record is None
    assert window.view_models == []
    assert voice_notifier.view_models == []


def test_controller_delegates_voice_enabled_change() -> None:

    runtime = FakeRuntimeService()
    window = FakeWindow()
    voice_notifier = FakeVoiceNotifier()

    controller = MainWindowController(
        runtime_service=runtime,
        presenter=SignalRecordPresenter(),
        voice_notifier=voice_notifier,
        window=window,
    )

    controller.set_voice_enabled(
        False,
    )
    controller.set_voice_enabled(
        True,
    )

    assert voice_notifier.enabled_changes == [
        False,
        True,
    ]


def test_controller_delegates_voice_test() -> None:

    runtime = FakeRuntimeService()
    window = FakeWindow()
    voice_notifier = FakeVoiceNotifier()

    controller = MainWindowController(
        runtime_service=runtime,
        presenter=SignalRecordPresenter(),
        voice_notifier=voice_notifier,
        window=window,
    )

    controller.test_voice()

    assert voice_notifier.test_voice_calls == 1


def test_controller_tracks_record_when_window_counts_new_signal() -> None:

    runtime = FakeRuntimeService(
        record=_record(),
    )
    window = FakeWindow()
    result_session = FakeManualResultSession()

    controller = MainWindowController(
        runtime_service=runtime,
        presenter=SignalRecordPresenter(),
        manual_result_session=result_session,
        window=window,
    )

    controller.run_once()

    assert result_session.tracked_records == [
        runtime.record,
    ]


def test_controller_does_not_track_rejected_or_duplicate_signal() -> None:

    runtime = FakeRuntimeService(
        record=_record(),
    )
    window = FakeWindow(
        accept_signal=False,
    )
    result_session = FakeManualResultSession()

    controller = MainWindowController(
        runtime_service=runtime,
        presenter=SignalRecordPresenter(),
        manual_result_session=result_session,
        window=window,
    )

    controller.run_once()

    assert result_session.tracked_records == []


def test_controller_persists_manual_result() -> None:

    runtime = FakeRuntimeService()
    window = FakeWindow()
    result_session = FakeManualResultSession()

    controller = MainWindowController(
        runtime_service=runtime,
        presenter=SignalRecordPresenter(),
        manual_result_session=result_session,
        window=window,
    )

    success = controller.register_manual_result(
        SessionResult.WIN,
    )

    assert success is True
    assert result_session.registered_results == [
        ManualSignalResult.WIN,
    ]


def test_controller_delegates_undo_and_reset() -> None:

    runtime = FakeRuntimeService()
    window = FakeWindow()
    result_session = FakeManualResultSession()

    controller = MainWindowController(
        runtime_service=runtime,
        presenter=SignalRecordPresenter(),
        manual_result_session=result_session,
        window=window,
    )

    assert controller.undo_manual_result() is True

    controller.reset_manual_result_session()

    assert result_session.undo_calls == 1
    assert result_session.reset_calls == 1


def test_controller_preserves_gui_state_when_result_persistence_fails() -> None:

    runtime = FakeRuntimeService()
    window = FakeWindow()
    result_session = FakeManualResultSession(
        error=OSError("disk unavailable"),
    )

    controller = MainWindowController(
        runtime_service=runtime,
        presenter=SignalRecordPresenter(),
        manual_result_session=result_session,
        window=window,
    )

    success = controller.register_manual_result(
        SessionResult.LOSS,
    )

    assert success is False
    assert (
        window.error_messages[-1] == "No fue posible guardar el resultado manual: "
        "disk unavailable"
    )


def test_controller_excludes_window_before_continuous_analysis() -> None:

    runtime = FakeRuntimeService()
    window = FakeWindow()
    worker = FakeWorker(
        auto_finish=False,
    )
    thread = FakeThread()
    excluder = FakeWindowCaptureExcluder()

    controller = MainWindowController(
        runtime_service=runtime,
        presenter=SignalRecordPresenter(),
        window_capture_excluder=excluder,
        window=window,
        worker_factory=lambda runtime_service: worker,
        thread_factory=lambda: thread,
    )

    controller.start()

    assert excluder.excluded_handles == [
        window.native_window_handle,
    ]
    assert thread.start_calls == 1
    assert worker.run_calls == 1


def test_controller_does_not_start_when_capture_exclusion_fails() -> None:

    runtime = FakeRuntimeService()
    window = FakeWindow()
    worker = FakeWorker(
        auto_finish=False,
    )
    thread = FakeThread()
    excluder = FakeWindowCaptureExcluder(
        result=False,
        error_code=5,
    )

    controller = MainWindowController(
        runtime_service=runtime,
        presenter=SignalRecordPresenter(),
        window_capture_excluder=excluder,
        window=window,
        worker_factory=lambda runtime_service: worker,
        thread_factory=lambda: thread,
    )

    controller.start()

    assert excluder.excluded_handles == [
        window.native_window_handle,
    ]
    assert thread.start_calls == 0
    assert worker.run_calls == 0
    assert window.running_states[-1] is False
    assert window.error_messages[-1] == (
        "No fue posible excluir la ventana del analizador "
        "de la captura continua. Código Win32: 5. "
        "Mueve la ventana fuera del gráfico o utiliza "
        "«Analizar una vez»."
    )


def test_controller_does_not_start_when_capture_excluder_raises() -> None:

    runtime = FakeRuntimeService()
    window = FakeWindow()
    worker = FakeWorker(
        auto_finish=False,
    )
    thread = FakeThread()
    excluder = FakeWindowCaptureExcluder(
        error=RuntimeError("affinity unavailable"),
    )

    controller = MainWindowController(
        runtime_service=runtime,
        presenter=SignalRecordPresenter(),
        window_capture_excluder=excluder,
        window=window,
        worker_factory=lambda runtime_service: worker,
        thread_factory=lambda: thread,
    )

    controller.start()

    assert thread.start_calls == 0
    assert worker.run_calls == 0
    assert window.running_states[-1] is False
    assert window.error_messages[-1] == (
        "No fue posible configurar la protección de captura: affinity unavailable"
    )


def test_controller_enables_and_disables_evidence_mode() -> None:

    runtime = FakeRuntimeService()
    window = FakeWindow()
    excluder = FakeWindowCaptureExcluder()

    controller = MainWindowController(
        runtime_service=runtime,
        presenter=SignalRecordPresenter(),
        window_capture_excluder=excluder,
        window=window,
    )

    assert (
        controller.set_evidence_mode(
            True,
        )
        is True
    )

    assert excluder.allowed_handles == [
        window.native_window_handle,
    ]

    assert (
        controller.set_evidence_mode(
            False,
        )
        is True
    )

    assert excluder.excluded_handles == [
        window.native_window_handle,
    ]


def test_controller_rejects_evidence_mode_while_analysis_is_running() -> None:

    runtime = FakeRuntimeService(
        is_running=True,
    )

    window = FakeWindow()
    excluder = FakeWindowCaptureExcluder()

    controller = MainWindowController(
        runtime_service=runtime,
        presenter=SignalRecordPresenter(),
        window_capture_excluder=excluder,
        window=window,
    )

    success = controller.set_evidence_mode(
        True,
    )

    assert success is False
    assert excluder.allowed_handles == []
    assert window.error_messages[-1] == (
        "Detén el análisis antes de activar el modo evidencia."
    )


def test_controller_blocks_start_while_evidence_mode_is_enabled() -> None:

    runtime = FakeRuntimeService()
    window = FakeWindow()
    worker = FakeWorker(
        auto_finish=False,
    )
    thread = FakeThread()
    excluder = FakeWindowCaptureExcluder()

    controller = MainWindowController(
        runtime_service=runtime,
        presenter=SignalRecordPresenter(),
        window_capture_excluder=excluder,
        window=window,
        worker_factory=lambda runtime_service: worker,
        thread_factory=lambda: thread,
    )

    assert (
        controller.set_evidence_mode(
            True,
        )
        is True
    )

    controller.start()

    assert thread.start_calls == 0
    assert worker.run_calls == 0
    assert window.error_messages[-1] == (
        "Restaura la protección de captura antes de iniciar el análisis."
    )


def test_controller_enables_recording_mode_when_location_is_safe() -> None:

    runtime = FakeRuntimeService()
    window = FakeWindow()
    excluder = FakeWindowCaptureExcluder()
    safety_guard = FakeRecordingSafetyGuard()

    controller = MainWindowController(
        runtime_service=runtime,
        presenter=SignalRecordPresenter(),
        window_capture_excluder=excluder,
        recording_safety_guard=safety_guard,
        window=window,
    )

    result = controller.set_recording_mode(
        True,
    )

    assert result is True
    assert safety_guard.received_handles == [
        window.native_window_handle,
    ]
    assert excluder.allowed_handles == [
        window.native_window_handle,
    ]


def test_controller_rejects_recording_mode_when_windows_overlap() -> None:

    runtime = FakeRuntimeService()
    window = FakeWindow()
    excluder = FakeWindowCaptureExcluder()
    safety_guard = FakeRecordingSafetyGuard(
        is_safe=False,
        message=("El analizador se superpone con Pocket Option."),
    )

    controller = MainWindowController(
        runtime_service=runtime,
        presenter=SignalRecordPresenter(),
        window_capture_excluder=excluder,
        recording_safety_guard=safety_guard,
        window=window,
    )

    result = controller.set_recording_mode(
        True,
    )

    assert result is False
    assert excluder.allowed_handles == []
    assert window.error_messages[-1] == (
        "El analizador se superpone con Pocket Option."
    )


def test_controller_starts_recording_without_excluding_window() -> None:

    runtime = FakeRuntimeService()
    window = FakeWindow()
    worker = FakeWorker(
        auto_finish=False,
    )
    thread = FakeThread()
    excluder = FakeWindowCaptureExcluder()
    safety_guard = FakeRecordingSafetyGuard()

    controller = MainWindowController(
        runtime_service=runtime,
        presenter=SignalRecordPresenter(),
        window_capture_excluder=excluder,
        recording_safety_guard=safety_guard,
        window=window,
        worker_factory=lambda runtime_service: worker,
        thread_factory=lambda: thread,
    )

    assert (
        controller.set_recording_mode(
            True,
        )
        is True
    )

    controller.start()

    assert thread.start_calls == 1
    assert worker.run_calls == 1
    assert excluder.allowed_handles == [
        window.native_window_handle,
    ]
    assert excluder.excluded_handles == []


def test_controller_blocks_start_when_recording_location_changed() -> None:

    runtime = FakeRuntimeService()
    window = FakeWindow()
    worker = FakeWorker(
        auto_finish=False,
    )
    thread = FakeThread()
    excluder = FakeWindowCaptureExcluder()
    safety_guard = FakeRecordingSafetyGuard()

    controller = MainWindowController(
        runtime_service=runtime,
        presenter=SignalRecordPresenter(),
        window_capture_excluder=excluder,
        recording_safety_guard=safety_guard,
        window=window,
        worker_factory=lambda runtime_service: worker,
        thread_factory=lambda: thread,
    )

    assert (
        controller.set_recording_mode(
            True,
        )
        is True
    )

    safety_guard.is_safe = False
    safety_guard.message = "El analizador se superpone con Pocket Option."

    controller.start()

    assert thread.start_calls == 0
    assert worker.run_calls == 0
    assert window.error_messages[-1] == (
        "El analizador se superpone con Pocket Option."
    )


def test_controller_rejects_evidence_mode_during_recording_mode() -> None:

    runtime = FakeRuntimeService()
    window = FakeWindow()
    excluder = FakeWindowCaptureExcluder()
    safety_guard = FakeRecordingSafetyGuard()

    controller = MainWindowController(
        runtime_service=runtime,
        presenter=SignalRecordPresenter(),
        window_capture_excluder=excluder,
        recording_safety_guard=safety_guard,
        window=window,
    )

    assert (
        controller.set_recording_mode(
            True,
        )
        is True
    )

    result = controller.set_evidence_mode(
        True,
    )

    assert result is False
    assert window.error_messages[-1] == (
        "Sal del modo grabación antes de activar el modo evidencia."
    )


def test_controller_suppresses_duplicate_side_effects() -> None:

    interval_started_at = datetime(
        2026,
        7,
        31,
        10,
        30,
        0,
        tzinfo=UTC,
    )

    duplicate_record = SignalRecord(
        signal=MarketSignal(
            direction=SignalDirection.CALL,
            strength=SignalStrength.HIGH,
            reason="Repeated confirmation.",
        ),
        created_at=datetime(
            2026,
            7,
            31,
            10,
            30,
            15,
            tzinfo=UTC,
        ),
        source="controller_test",
        disposition=(SignalRecordDisposition.DUPLICATE_SUPPRESSED),
        candle_interval_started_at=interval_started_at,
    )

    runtime = FakeRuntimeService(
        record=duplicate_record,
    )
    window = FakeWindow()
    voice = FakeVoiceNotifier()
    manual_session = FakeManualResultSession()

    controller = MainWindowController(
        runtime_service=runtime,
        presenter=SignalRecordPresenter(),
        voice_notifier=voice,
        manual_result_session=manual_session,
        window=window,
    )

    controller.run_once()

    assert window.view_models == []
    assert len(window.diagnostic_view_models) == 1
    assert voice.view_models == []
    assert manual_session.tracked_records == []
    assert len(window.gate_audit_view_models) == 1

    assert "1 duplicada suprimida" in window.gate_audit_view_models[-1].text


def test_controller_resets_voice_for_new_accepted_interval() -> None:

    interval_started_at = datetime(
        2026,
        7,
        31,
        10,
        30,
        30,
        tzinfo=UTC,
    )

    accepted_record = SignalRecord(
        signal=MarketSignal(
            direction=SignalDirection.CALL,
            strength=SignalStrength.HIGH,
            reason="New candle confirmation.",
        ),
        created_at=datetime(
            2026,
            7,
            31,
            10,
            30,
            35,
            tzinfo=UTC,
        ),
        source="controller_test",
        disposition=(SignalRecordDisposition.ACTIONABLE_ACCEPTED),
        candle_interval_started_at=interval_started_at,
    )

    runtime = FakeRuntimeService(
        record=accepted_record,
    )
    window = FakeWindow()
    voice = FakeVoiceNotifier()

    controller = MainWindowController(
        runtime_service=runtime,
        presenter=SignalRecordPresenter(),
        voice_notifier=voice,
        window=window,
    )

    controller.run_once()

    assert voice.reset_calls == 1
    assert len(voice.view_models) == 1
    assert voice.view_models[0].is_actionable is True
    assert len(window.gate_audit_view_models) == 1

    assert "1 aceptada" in window.gate_audit_view_models[-1].text
