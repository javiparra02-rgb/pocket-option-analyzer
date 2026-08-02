from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

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


class FakeAnalysisUseCase:
    def __init__(self) -> None:
        self.received_frames = []

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
    )

    record = service.run_once()

    assert record is not None
    assert record.signal.direction is SignalDirection.CALL
    assert record.created_at is frame.captured_at
    assert analysis_use_case.received_frames == [
        frame,
    ]


def test_run_once_returns_none_when_capture_has_no_frame() -> None:

    capture_service = FakeCaptureService(
        frames=[],
    )
    analysis_use_case = FakeAnalysisUseCase()

    service = FrameAnalysisLoopService(
        capture_service=capture_service,
        analysis_use_case=analysis_use_case,
    )

    record = service.run_once()

    assert record is None
    assert analysis_use_case.received_frames == []


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
