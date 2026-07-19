from __future__ import annotations

from datetime import datetime, timezone

from pocket_option_analyzer.domain.signals import (
    MarketSignal,
    SignalDirection,
    SignalRecord,
    SignalStrength,
)
from pocket_option_analyzer.presentation.gui import (
    MainWindowController,
)
from pocket_option_analyzer.presentation.signals import (
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
    ) -> None:
        self._is_running = False
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

    def __init__(self) -> None:
        self.running_states: list[bool] = []
        self.view_models = []
        self.error_messages: list[str | None] = []
        self.hide_for_capture_calls = 0
        self.show_after_capture_calls = 0

    def set_running_state(
        self,
        is_running: bool,
    ) -> None:
        self.running_states.append(is_running)

    def update_signal(
        self,
        view_model,
    ) -> None:
        self.view_models.append(view_model)

    def set_error_message(
        self,
        message: str | None,
    ) -> None:
        self.error_messages.append(message)
    
    def hide_for_capture(self) -> None:
        self.hide_for_capture_calls += 1

    def show_after_capture(self) -> None:
        self.show_after_capture_calls += 1


class FakeVoiceNotifier:

    def __init__(self) -> None:
        self.view_models = []

    def notify(
        self,
        view_model,
    ) -> None:
        self.view_models.append(
            view_model,
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
            tzinfo=timezone.utc,
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