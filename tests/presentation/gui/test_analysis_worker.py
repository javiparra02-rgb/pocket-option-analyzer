from __future__ import annotations

from datetime import UTC, datetime
from threading import Event, Thread

import pytest

from pocket_option_analyzer.domain.signals import (
    MarketSignal,
    SignalDirection,
    SignalRecord,
    SignalStrength,
)
from pocket_option_analyzer.presentation.gui import (
    AnalysisWorker,
)


class FakeRuntimeService:
    def __init__(
        self,
        records,
        error: Exception | None = None,
        owns_session: bool = True,
    ) -> None:
        self._records = list(records)
        self._error = error
        self._owns_session = owns_session
        self.run_once_calls = 0
        self.start_session_calls = 0
        self.stop_session_calls = 0

    def start_session(self) -> bool:
        self.start_session_calls += 1
        return self._owns_session

    def stop_session(self) -> None:
        self.stop_session_calls += 1

    def run_once(self):
        self.run_once_calls += 1

        if self._error is not None:
            raise self._error

        if not self._records:
            return None

        return self._records.pop(0)


class BlockingRuntimeService:
    """
    Runtime que avisa cuando completó su primera iteración.

    Permite comprobar la espera interrumpible sin depender de pausas
    arbitrarias dentro del test.
    """

    def __init__(
        self,
    ) -> None:
        self.run_once_calls = 0
        self.first_iteration_completed = Event()
        self.start_session_calls = 0
        self.stop_session_calls = 0

    def start_session(self) -> bool:
        self.start_session_calls += 1
        return True

    def stop_session(self) -> None:
        self.stop_session_calls += 1

    def run_once(
        self,
    ) -> None:
        self.run_once_calls += 1

        self.first_iteration_completed.set()

        return None


class SignalCollector:
    def __init__(self) -> None:
        self.records = []
        self.errors: list[str] = []
        self.running_states: list[bool] = []
        self.finished_calls = 0

    def collect_record(
        self,
        record,
    ) -> None:
        self.records.append(record)

    def collect_error(
        self,
        message: str,
    ) -> None:
        self.errors.append(message)

    def collect_running_state(
        self,
        is_running: bool,
    ) -> None:
        self.running_states.append(is_running)

    def collect_finished(self) -> None:
        self.finished_calls += 1


class FakeSleep:
    def __init__(self) -> None:
        self.calls: list[float] = []

    def __call__(
        self,
        seconds: float,
    ) -> None:
        self.calls.append(seconds)


class StopWorkerSleep:
    def __init__(self) -> None:
        self.worker: AnalysisWorker | None = None
        self.calls: list[float] = []

    def __call__(
        self,
        seconds: float,
    ) -> None:
        self.calls.append(seconds)

        assert self.worker is not None

        self.worker.stop()


def _record(
    direction: SignalDirection = SignalDirection.CALL,
) -> SignalRecord:

    return SignalRecord(
        signal=MarketSignal(
            direction=direction,
            strength=SignalStrength.HIGH,
            reason="Worker test signal.",
        ),
        created_at=datetime(
            2026,
            1,
            1,
            tzinfo=UTC,
        ),
        source="worker_test",
    )


def _connect(
    worker: AnalysisWorker,
    collector: SignalCollector,
) -> None:

    worker.record_ready.connect(
        collector.collect_record,
    )
    worker.error_occurred.connect(
        collector.collect_error,
    )
    worker.running_changed.connect(
        collector.collect_running_state,
    )
    worker.finished.connect(
        collector.collect_finished,
    )


def test_worker_emits_records_and_running_state() -> None:

    sleep = FakeSleep()
    collector = SignalCollector()
    runtime = FakeRuntimeService(
        records=[
            _record(),
            _record(
                direction=SignalDirection.PUT,
            ),
        ],
    )

    worker = AnalysisWorker(
        runtime_service=runtime,
        interval_seconds=0.5,
        sleep_function=sleep,
    )

    _connect(
        worker=worker,
        collector=collector,
    )

    worker.run(
        max_iterations=2,
    )

    assert worker.is_running is False
    assert len(collector.records) == 2
    assert collector.records[0].signal.direction is SignalDirection.CALL
    assert collector.records[1].signal.direction is SignalDirection.PUT
    assert collector.running_states == [
        True,
        False,
    ]
    assert collector.finished_calls == 1
    assert runtime.start_session_calls == 1
    assert runtime.stop_session_calls == 1
    assert sleep.calls == [
        0.5,
    ]


def test_worker_ignores_empty_records() -> None:

    collector = SignalCollector()

    worker = AnalysisWorker(
        runtime_service=FakeRuntimeService(
            records=[
                None,
                _record(),
            ],
        ),
        interval_seconds=0.0,
        sleep_function=FakeSleep(),
    )

    _connect(
        worker=worker,
        collector=collector,
    )

    worker.run(
        max_iterations=2,
    )

    assert len(collector.records) == 1
    assert collector.records[0].signal.direction is SignalDirection.CALL


def test_worker_can_be_stopped_from_sleep_callback() -> None:

    sleep = StopWorkerSleep()
    collector = SignalCollector()

    worker = AnalysisWorker(
        runtime_service=FakeRuntimeService(
            records=[
                _record(),
                _record(),
                _record(),
            ],
        ),
        interval_seconds=0.1,
        sleep_function=sleep,
    )

    sleep.worker = worker

    _connect(
        worker=worker,
        collector=collector,
    )

    worker.run()

    assert worker.is_running is False
    assert len(collector.records) == 1
    assert sleep.calls == [
        0.1,
    ]
    assert collector.running_states == [
        True,
        False,
    ]


def test_worker_emits_error_and_finishes() -> None:

    collector = SignalCollector()
    runtime = FakeRuntimeService(
        records=[],
        error=RuntimeError("capture failed"),
    )

    worker = AnalysisWorker(
        runtime_service=runtime,
        interval_seconds=0.0,
        sleep_function=FakeSleep(),
    )

    _connect(
        worker=worker,
        collector=collector,
    )

    worker.run()

    assert worker.is_running is False
    assert collector.errors == [
        "capture failed",
    ]
    assert collector.finished_calls == 1
    assert runtime.start_session_calls == 1
    assert runtime.stop_session_calls == 1


def test_worker_does_not_stop_session_owned_by_another_controller() -> None:
    runtime = FakeRuntimeService(records=[None], owns_session=False)
    worker = AnalysisWorker(
        runtime_service=runtime,
        interval_seconds=0.0,
        sleep_function=FakeSleep(),
    )

    worker.run(max_iterations=1)

    assert runtime.start_session_calls == 1
    assert runtime.stop_session_calls == 0


def test_worker_rejects_negative_interval() -> None:

    with pytest.raises(
        ValueError,
        match="Worker interval seconds cannot be negative.",
    ):
        AnalysisWorker(
            runtime_service=FakeRuntimeService(
                records=[],
            ),
            interval_seconds=-1.0,
        )


def test_worker_runs_analysis_when_iteration_guard_accepts() -> None:

    runtime = FakeRuntimeService(
        records=[],
    )
    guard_calls = 0

    def guard() -> None:
        nonlocal guard_calls
        guard_calls += 1
        return None

    worker = AnalysisWorker(
        runtime_service=runtime,
        interval_seconds=0,
        sleep_function=lambda seconds: None,
        iteration_guard=guard,
    )

    worker.run(
        max_iterations=1,
    )

    assert guard_calls == 1
    assert runtime.run_once_calls == 1


def test_worker_stops_before_capture_when_iteration_guard_rejects() -> None:

    runtime = FakeRuntimeService(
        records=[],
    )
    errors: list[str] = []

    worker = AnalysisWorker(
        runtime_service=runtime,
        interval_seconds=0,
        sleep_function=lambda seconds: None,
        iteration_guard=lambda: "El analizador se superpone con Pocket Option.",
    )

    worker.error_occurred.connect(
        errors.append,
    )

    worker.run(
        max_iterations=1,
    )

    assert runtime.run_once_calls == 0
    assert errors == [
        "El analizador se superpone con Pocket Option.",
    ]


def test_worker_honors_stop_requested_before_run() -> None:

    runtime = FakeRuntimeService(
        records=[
            _record(),
        ],
    )
    collector = SignalCollector()

    worker = AnalysisWorker(
        runtime_service=runtime,
        interval_seconds=0.0,
    )

    _connect(
        worker=worker,
        collector=collector,
    )

    worker.stop()
    worker.run()

    assert runtime.run_once_calls == 0
    assert worker.is_running is False
    assert collector.records == []
    assert collector.errors == []
    assert collector.running_states == []
    assert collector.finished_calls == 1


def test_worker_stop_interrupts_default_wait() -> None:

    runtime = BlockingRuntimeService()

    worker = AnalysisWorker(
        runtime_service=runtime,
        interval_seconds=60.0,
    )

    worker_thread = Thread(
        target=worker.run,
        daemon=True,
    )

    worker_thread.start()

    first_iteration_completed = runtime.first_iteration_completed.wait(
        timeout=1.0,
    )

    assert first_iteration_completed is True

    worker.stop()

    worker_thread.join(
        timeout=1.0,
    )

    assert not worker_thread.is_alive()
    assert runtime.run_once_calls == 1
    assert worker.is_running is False
