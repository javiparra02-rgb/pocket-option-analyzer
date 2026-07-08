from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np

from pocket_option_analyzer.domain.signals import (
    SignalDirection,
    SignalHistory,
)
from pocket_option_analyzer.infrastructure.bootstrap import (
    PocketOptionRuntimeFactory,
    WindowLocatorReaderAdapter,
)
from pocket_option_analyzer.vision.models import ChartRegion

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

    def capture_once(
        self,
    ):
        if not self._frames:
            return None

        return self._frames.pop(0)


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
            tzinfo=timezone.utc,
        ),
    )


def test_pocket_option_runtime_factory_creates_runtime_with_injected_capture_service() -> None:

    history = SignalHistory()
    frame = _frame()

    runtime_service = PocketOptionRuntimeFactory.create_runtime_service(
        capture_service=FakeCaptureService(
            frames=[
                frame,
            ],
        ),
        signal_history=history,
        signal_file_path=None,
        interval_seconds=0.0,
    )

    record = runtime_service.run_once()

    assert record is not None
    assert history.latest() is record
    assert record.signal.direction is SignalDirection.NONE
    assert record.created_at is frame.captured_at
    assert record.source == "captured_frame_visual_analysis"


def test_pocket_option_runtime_factory_writes_jsonl_when_path_is_configured(
    tmp_path,
) -> None:

    history = SignalHistory()
    file_path = tmp_path / "signals" / "signals.jsonl"

    runtime_service = PocketOptionRuntimeFactory.create_runtime_service(
        capture_service=FakeCaptureService(
            frames=[
                _frame(),
            ],
        ),
        signal_history=history,
        signal_file_path=file_path,
        interval_seconds=0.0,
    )

    record = runtime_service.run_once()

    assert record is not None
    assert history.latest() is record
    assert file_path.exists()


class FakeWindowLocator:

    def __init__(self) -> None:
        self.received_title = None

    def locate(
        self,
        window_title: str,
    ):
        self.received_title = window_title

        return "fake_window"


def test_window_locator_reader_adapter_delegates_to_locator() -> None:

    locator = FakeWindowLocator()

    adapter = WindowLocatorReaderAdapter(
        locator=locator,
    )

    result = adapter.read(
        "Pocket Option",
    )

    assert result == "fake_window"
    assert locator.received_title == "Pocket Option"


def test_pocket_option_runtime_factory_creates_real_capture_service() -> None:

    capture_service = PocketOptionRuntimeFactory.create_capture_service(
        window_title="Pocket Option",
        chart_region=ChartRegion(
            x=0,
            y=0,
            width=100,
            height=100,
        ),
    )

    assert capture_service is not None