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


class FakeRuntimeService:

    def __init__(
        self,
        record: SignalRecord | None = None,
    ) -> None:
        self._is_running = False
        self.record = record
        self.start_calls = 0
        self.stop_calls = 0
        self.run_once_calls = 0

    @property
    def is_running(self) -> bool:
        return self._is_running

    def start(self) -> None:
        self.start_calls += 1
        self._is_running = True

    def stop(self) -> None:
        self.stop_calls += 1
        self._is_running = False

    def run_once(self) -> SignalRecord | None:
        self.run_once_calls += 1
        return self.record


class FakeWindow:

    def __init__(self) -> None:
        self.running_states: list[bool] = []
        self.view_models = []

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


def test_controller_starts_runtime_and_updates_window_state() -> None:

    runtime = FakeRuntimeService()
    window = FakeWindow()

    controller = MainWindowController(
        runtime_service=runtime,
        presenter=SignalRecordPresenter(),
        window=window,
    )

    controller.start()

    assert runtime.start_calls == 1
    assert window.running_states == [
        False,
        True,
    ]


def test_controller_stops_runtime_and_updates_window_state() -> None:

    runtime = FakeRuntimeService()
    window = FakeWindow()

    controller = MainWindowController(
        runtime_service=runtime,
        presenter=SignalRecordPresenter(),
        window=window,
    )

    controller.start()
    controller.stop()

    assert runtime.stop_calls == 1
    assert window.running_states == [
        False,
        True,
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