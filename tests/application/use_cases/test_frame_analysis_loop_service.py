from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Event, Thread

import numpy as np
import pytest

from pocket_option_analyzer.application.use_cases import (
    FrameAnalysisLoopService,
)
from pocket_option_analyzer.domain.signals import (
    MarketSignal,
    SignalDirection,
    SignalRecord,
    SignalStrength,
)


@dataclass(frozen=True, slots=True)
class FakeFrame:
    image: np.ndarray

    captured_at: datetime


class FakeCaptureService:
    def __init__(
        self,
        frames,
    ) -> None:
        self._frames = list(frames)
        self.capture_calls = 0

    def capture_once(
        self,
    ):
        self.capture_calls += 1

        if not self._frames:
            return None

        return self._frames.pop(0)


class SynchronizedCaptureService(FakeCaptureService):
    """
    Captura falsa que informa cuándo terminó la primera captura.

    Evita usar pausas arbitrarias para sincronizar los tests con el
    hilo donde se ejecuta FrameAnalysisLoopService.
    """

    def __init__(
        self,
        frames,
    ) -> None:
        super().__init__(
            frames=frames,
        )
        self.first_capture_completed = Event()

    def capture_once(
        self,
    ):
        frame = super().capture_once()

        self.first_capture_completed.set()

        return frame


class FakeAnalysisUseCase:
    def __init__(self) -> None:
        self.received_frames = []
        self.started_sessions: list[str] = []
        self.stop_session_calls = 0

    def start_session(self, *, session_key: str) -> None:
        self.started_sessions.append(session_key)

    def stop_session(self) -> None:
        self.stop_session_calls += 1

    def execute(
        self,
        frame,
    ) -> SignalRecord:
        self.received_frames.append(frame)

        return SignalRecord(
            signal=MarketSignal(
                direction=SignalDirection.CALL,
                strength=SignalStrength.HIGH,
                reason="Frame analyzed.",
            ),
            created_at=frame.captured_at,
            source="test_loop",
        )


class FailingAnalysisUseCase(FakeAnalysisUseCase):
    def execute(self, frame) -> SignalRecord:
        raise RuntimeError("analysis failed")


class FakeSleep:
    def __init__(self) -> None:
        self.calls: list[float] = []

    def __call__(
        self,
        seconds: float,
    ) -> None:
        self.calls.append(seconds)


def _frame() -> FakeFrame:

    return FakeFrame(
        image=np.zeros(
            (100, 100, 3),
            dtype=np.uint8,
        ),
        captured_at=datetime(
            2026,
            1,
            1,
            tzinfo=UTC,
        ),
    )


def test_run_once_captures_analyzes_and_returns_record() -> None:

    frame = _frame()

    capture_service = FakeCaptureService(
        frames=[
            frame,
        ],
    )
    analysis_use_case = FakeAnalysisUseCase()

    service = FrameAnalysisLoopService(
        capture_service=capture_service,
        analysis_use_case=analysis_use_case,
        session_key_factory=lambda: "one-shot-session",
    )

    record = service.run_once()

    assert record is not None
    assert record.signal.direction is SignalDirection.CALL
    assert record.created_at is frame.captured_at
    assert analysis_use_case.received_frames == [
        frame,
    ]
    assert analysis_use_case.started_sessions == ["one-shot-session"]
    assert analysis_use_case.stop_session_calls == 1


def test_run_once_returns_none_when_capture_has_no_frame() -> None:

    capture_service = FakeCaptureService(
        frames=[],
    )
    analysis_use_case = FakeAnalysisUseCase()

    service = FrameAnalysisLoopService(
        capture_service=capture_service,
        analysis_use_case=analysis_use_case,
        session_key_factory=lambda: "empty-one-shot",
    )

    record = service.run_once()

    assert record is None
    assert analysis_use_case.received_frames == []
    assert analysis_use_case.started_sessions == ["empty-one-shot"]
    assert analysis_use_case.stop_session_calls == 1


def test_start_runs_until_max_iterations() -> None:

    frames = [
        _frame(),
        _frame(),
        _frame(),
    ]

    capture_service = FakeCaptureService(
        frames=frames,
    )
    analysis_use_case = FakeAnalysisUseCase()
    sleep = FakeSleep()

    service = FrameAnalysisLoopService(
        capture_service=capture_service,
        analysis_use_case=analysis_use_case,
        interval_seconds=0.5,
        sleep_function=sleep,
        session_key_factory=lambda: "continuous-session",
    )

    service.start(
        max_iterations=3,
    )

    assert service.is_running is False
    assert capture_service.capture_calls == 3
    assert len(analysis_use_case.received_frames) == 3
    assert sleep.calls == [
        0.5,
        0.5,
    ]
    assert analysis_use_case.started_sessions == ["continuous-session"]
    assert analysis_use_case.stop_session_calls == 1


def test_service_rejects_negative_interval() -> None:

    with pytest.raises(
        ValueError,
        match="Loop interval seconds cannot be negative.",
    ):
        FrameAnalysisLoopService(
            capture_service=FakeCaptureService(
                frames=[],
            ),
            analysis_use_case=FakeAnalysisUseCase(),
            interval_seconds=-1.0,
        )


def test_stop_interrupts_default_wait_and_service_can_restart() -> None:

    capture_service = SynchronizedCaptureService(
        frames=[
            _frame(),
            _frame(),
        ],
    )
    analysis_use_case = FakeAnalysisUseCase()

    service = FrameAnalysisLoopService(
        capture_service=capture_service,
        analysis_use_case=analysis_use_case,
        interval_seconds=60.0,
    )

    service_thread = Thread(
        target=service.start,
        daemon=True,
    )

    service_thread.start()

    first_capture_completed = capture_service.first_capture_completed.wait(
        timeout=1.0,
    )

    assert first_capture_completed is True
    assert service.is_running is True
    assert capture_service.capture_calls == 1

    service.stop()

    service_thread.join(
        timeout=1.0,
    )

    assert not service_thread.is_alive()
    assert service.is_running is False
    assert capture_service.capture_calls == 1
    assert len(analysis_use_case.received_frames) == 1

    service.start(
        max_iterations=1,
    )

    assert service.is_running is False
    assert capture_service.capture_calls == 2
    assert len(analysis_use_case.received_frames) == 2
    assert len(analysis_use_case.started_sessions) == 2
    assert analysis_use_case.started_sessions[0] != (
        analysis_use_case.started_sessions[1]
    )
    assert analysis_use_case.stop_session_calls == 2


def test_service_ignores_concurrent_start() -> None:

    capture_service = SynchronizedCaptureService(
        frames=[
            _frame(),
            _frame(),
        ],
    )
    analysis_use_case = FakeAnalysisUseCase()

    service = FrameAnalysisLoopService(
        capture_service=capture_service,
        analysis_use_case=analysis_use_case,
        interval_seconds=60.0,
    )

    service_thread = Thread(
        target=service.start,
        daemon=True,
    )

    service_thread.start()

    first_capture_completed = capture_service.first_capture_completed.wait(
        timeout=1.0,
    )

    assert first_capture_completed is True
    assert service.is_running is True
    assert capture_service.capture_calls == 1

    service.start(
        max_iterations=1,
    )

    assert capture_service.capture_calls == 1
    assert len(analysis_use_case.received_frames) == 1

    service.stop()

    service_thread.join(
        timeout=1.0,
    )

    assert not service_thread.is_alive()
    assert service.is_running is False


def test_session_is_stopped_when_analysis_raises() -> None:
    analysis_use_case = FailingAnalysisUseCase()
    service = FrameAnalysisLoopService(
        capture_service=FakeCaptureService(frames=[_frame()]),
        analysis_use_case=analysis_use_case,
        session_key_factory=lambda: "failed-session",
    )

    with pytest.raises(RuntimeError, match="analysis failed"):
        service.start(max_iterations=1)

    assert service.is_running is False
    assert analysis_use_case.started_sessions == ["failed-session"]
    assert analysis_use_case.stop_session_calls == 1
