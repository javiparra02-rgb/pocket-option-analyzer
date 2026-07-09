from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np

from pocket_option_analyzer.domain.signals import (
    SignalDirection,
    SignalHistory,
)
from pocket_option_analyzer.infrastructure.bootstrap import (
    FixedChartRegionExtractor,
    PocketOptionChartRegionExtractor,
    PocketOptionRuntimeFactory,
    RuntimeRoiDebugCapture,
    RuntimeWindowFinder,
    RuntimeWindowHandle,
    RuntimeWindowInfo,
    RuntimeWindowReader,
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


def test_runtime_window_finder_returns_best_title_match() -> None:

    finder = RuntimeWindowFinder(
        window_provider=lambda: [
            RuntimeWindowHandle(
                hwnd=1,
                title="Other Window",
                width=500,
                height=500,
            ),
            RuntimeWindowHandle(
                hwnd=2,
                title="Pocket Option - Small",
                width=300,
                height=300,
            ),
            RuntimeWindowHandle(
                hwnd=3,
                title="Pocket Option - Large",
                width=1000,
                height=800,
            ),
        ],
    )

    result = finder.find(
        "Pocket Option",
    )

    assert result is not None
    assert result.hwnd == 3


def test_runtime_window_finder_returns_none_when_no_match_exists() -> None:

    finder = RuntimeWindowFinder(
        window_provider=lambda: [
            RuntimeWindowHandle(
                hwnd=1,
                title="Other Window",
                width=500,
                height=500,
            ),
        ],
    )

    result = finder.find(
        "Pocket Option",
    )

    assert result is None


def test_runtime_window_reader_returns_window_info_from_provider() -> None:

    expected = RuntimeWindowInfo(
        hwnd=123,
        title="Pocket Option",
        left=10,
        top=20,
        width=300,
        height=200,
    )

    reader = RuntimeWindowReader(
        info_provider=lambda hwnd: expected,
    )

    result = reader.read(
        hwnd=123,
    )

    assert result is expected
    assert result.left == 10
    assert result.top == 20
    assert result.width == 300
    assert result.height == 200


def test_fixed_chart_region_extractor_returns_clamped_region() -> None:

    extractor = FixedChartRegionExtractor(
        region=ChartRegion(
            x=10,
            y=20,
            width=500,
            height=400,
        ),
    )

    image = np.zeros(
        (100, 200, 3),
        dtype=np.uint8,
    )

    region = extractor.extract(
        image=image,
    )

    assert region.x == 10
    assert region.y == 20
    assert region.width == 190
    assert region.height == 80


def test_pocket_option_chart_region_extractor_returns_main_chart_area() -> None:

    extractor = PocketOptionChartRegionExtractor()

    image = np.zeros(
        (900, 1600, 3),
        dtype=np.uint8,
    )

    region = extractor.extract(
        image=image,
    )

    assert region.x == 0
    assert region.y == 63
    assert region.width == 1504
    assert region.height == 711



def test_runtime_roi_debug_capture_saves_image(
    tmp_path,
) -> None:

    capture = RuntimeRoiDebugCapture(
        directory=tmp_path,
        filename_prefix="test_roi",
    )

    image = np.zeros(
        (20, 30, 3),
        dtype=np.uint8,
    )

    capture.save(
        image=image,
    )

    assert capture.latest_path is not None
    assert capture.latest_path.exists()
    assert capture.latest_path.name.startswith(
        "test_roi_",
    )
    assert capture.latest_path.suffix == ".png"


def test_pocket_option_runtime_factory_disables_roi_debug_by_default() -> None:

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

    
def test_pocket_option_runtime_factory_can_enable_roi_debug(
    tmp_path,
) -> None:

    capture_service = PocketOptionRuntimeFactory.create_capture_service(
        window_title="Pocket Option",
        chart_region=ChartRegion(
            x=0,
            y=0,
            width=100,
            height=100,
        ),
        debug_roi_directory=tmp_path,
    )

    assert capture_service is not None