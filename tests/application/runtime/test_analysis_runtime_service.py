from __future__ import annotations

from datetime import datetime, timezone

from pocket_option_analyzer.application.runtime import (
    AnalysisRuntimeService,
)
from pocket_option_analyzer.domain.signals import (
    MarketSignal,
    SignalDirection,
    SignalRecord,
    SignalStrength,
)


class FakeFrameAnalysisLoop:

    def __init__(self) -> None:
        self._is_running = False
        self.run_once_calls = 0
        self.start_calls = []
        self.stop_calls = 0

    @property
    def is_running(self) -> bool:
        return self._is_running

    def run_once(self) -> SignalRecord:
        self.run_once_calls += 1

        return SignalRecord(
            signal=MarketSignal(
                direction=SignalDirection.CALL,
                strength=SignalStrength.HIGH,
                reason="Runtime test signal.",
            ),
            created_at=datetime(
                2026,
                1,
                1,
                tzinfo=timezone.utc,
            ),
            source="runtime_test",
        )

    def start(
        self,
        max_iterations: int | None = None,
    ) -> None:
        self._is_running = True
        self.start_calls.append(max_iterations)

    def stop(self) -> None:
        self._is_running = False
        self.stop_calls += 1


def test_runtime_service_delegates_run_once() -> None:

    loop = FakeFrameAnalysisLoop()

    service = AnalysisRuntimeService(
        loop_service=loop,
    )

    record = service.run_once()

    assert record is not None
    assert record.signal.direction is SignalDirection.CALL
    assert record.signal.strength is SignalStrength.HIGH
    assert record.source == "runtime_test"
    assert loop.run_once_calls == 1


def test_runtime_service_delegates_start() -> None:

    loop = FakeFrameAnalysisLoop()

    service = AnalysisRuntimeService(
        loop_service=loop,
    )

    service.start(
        max_iterations=3,
    )

    assert service.is_running is True
    assert loop.start_calls == [
        3,
    ]


def test_runtime_service_delegates_stop() -> None:

    loop = FakeFrameAnalysisLoop()
    service = AnalysisRuntimeService(
        loop_service=loop,
    )

    service.start()
    service.stop()

    assert service.is_running is False
    assert loop.stop_calls == 1


def test_runtime_service_exposes_running_state() -> None:

    loop = FakeFrameAnalysisLoop()

    service = AnalysisRuntimeService(
        loop_service=loop,
    )

    assert service.is_running is False

    service.start()

    assert service.is_running is True