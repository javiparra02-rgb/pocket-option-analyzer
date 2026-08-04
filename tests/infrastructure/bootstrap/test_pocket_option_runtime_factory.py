from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import count
from pathlib import Path

import numpy as np
import pytest

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


def _write_debug_image(
    path: str,
    _image: np.ndarray,
) -> bool:
    Path(
        path,
    ).write_bytes(
        b"runtime-roi-debug-image",
    )

    return True


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


def test_pocket_option_runtime_factory_creates_runtime_with_injected_capture_service() -> (  # noqa: E501
    None
):

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


def test_runtime_window_finder_ignores_invalid_capture_candidates() -> None:

    finder = RuntimeWindowFinder(
        window_provider=lambda: [
            RuntimeWindowHandle(
                hwnd=1,
                title="Pocket Option - Invisible",
                width=2000,
                height=1000,
                visible=False,
            ),
            RuntimeWindowHandle(
                hwnd=2,
                title="Pocket Option - Minimized",
                width=1900,
                height=900,
                minimized=True,
            ),
            RuntimeWindowHandle(
                hwnd=3,
                title="Pocket Option - Empty Width",
                width=0,
                height=800,
            ),
            RuntimeWindowHandle(
                hwnd=0,
                title="Pocket Option - Invalid HWND",
                width=1600,
                height=900,
            ),
            RuntimeWindowHandle(
                hwnd=5,
                title="Pocket Option - Valid",
                width=1200,
                height=700,
            ),
        ],
    )

    result = finder.find(
        "Pocket Option",
    )

    assert result is not None
    assert result.hwnd == 5
    assert result.is_capture_candidate is True
    assert result.area == 840_000


def test_runtime_window_finder_returns_none_when_matches_are_not_capturable() -> None:

    finder = RuntimeWindowFinder(
        window_provider=lambda: [
            RuntimeWindowHandle(
                hwnd=1,
                title="Pocket Option - Minimized",
                width=1200,
                height=800,
                minimized=True,
            ),
            RuntimeWindowHandle(
                hwnd=2,
                title="Pocket Option - Invalid Size",
                width=-1,
                height=800,
            ),
        ],
    )

    result = finder.find(
        "Pocket Option",
    )

    assert result is None


def test_runtime_window_finder_rejects_empty_search_without_enumerating() -> None:

    provider_called = False

    def window_provider():
        nonlocal provider_called

        provider_called = True

        return [
            RuntimeWindowHandle(
                hwnd=1,
                title="Pocket Option",
                width=1200,
                height=800,
            )
        ]

    finder = RuntimeWindowFinder(
        window_provider=window_provider,
    )

    result = finder.find(
        "   ",
    )

    assert result is None
    assert provider_called is False


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


def test_pocket_option_chart_region_extractor_returns_candle_chart_area() -> None:

    extractor = PocketOptionChartRegionExtractor()

    image = np.zeros(
        (
            900,
            1600,
            3,
        ),
        dtype=np.uint8,
    )

    region = extractor.extract(
        image=image,
    )

    assert region.x == 0
    assert region.y == 90
    assert region.width == 1376
    assert region.height == 675
    assert region.y + region.height == 765


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


def test_runtime_roi_debug_capture_keeps_directory_bounded_during_long_session(
    tmp_path,
) -> None:

    fixed_timestamp = datetime(
        2026,
        8,
        3,
        21,
        3,
        14,
        tzinfo=UTC,
    )

    sequence = count()

    capture = RuntimeRoiDebugCapture(
        directory=tmp_path,
        filename_prefix="roi",
        max_files=3,
        clock=lambda: fixed_timestamp,
        token_factory=lambda: f"{next(sequence):04d}",
        image_writer=_write_debug_image,
    )

    image = np.zeros(
        (20, 30, 3),
        dtype=np.uint8,
    )

    for _ in range(
        100,
    ):
        capture.save(
            image=image,
        )

        assert (
            len(
                list(
                    tmp_path.glob(
                        "roi_*.png",
                    )
                )
            )
            <= 3
        )

    retained_paths = sorted(
        tmp_path.glob(
            "roi_*.png",
        )
    )

    assert [path.name for path in retained_paths] == [
        "roi_20260803_210314_000000_0097.png",
        "roi_20260803_210314_000000_0098.png",
        "roi_20260803_210314_000000_0099.png",
    ]

    assert capture.latest_path == retained_paths[-1]
    assert capture.max_files == 3


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


def test_pocket_option_chart_region_extractor_excludes_lower_indicators() -> None:

    extractor = PocketOptionChartRegionExtractor()

    image = np.zeros(
        (
            1000,
            1600,
            3,
        ),
        dtype=np.uint8,
    )

    region = extractor.extract(
        image=image,
    )

    assert region.y == 100
    assert region.width == 1376
    assert region.height == 750
    assert region.y + region.height == 850


def test_runtime_roi_debug_capture_preserves_unrelated_files(
    tmp_path,
) -> None:

    unrelated_text = tmp_path / "notes.txt"
    unrelated_image = tmp_path / "other_20260803_210314_000000.png"

    unrelated_text.write_text(
        "keep",
        encoding="utf-8",
    )
    unrelated_image.write_bytes(
        b"keep-other-image",
    )

    tokens = iter(
        (
            "first",
            "second",
        )
    )

    capture = RuntimeRoiDebugCapture(
        directory=tmp_path,
        filename_prefix="roi",
        max_files=1,
        clock=lambda: datetime(
            2026,
            8,
            3,
            21,
            3,
            14,
            tzinfo=UTC,
        ),
        token_factory=lambda: next(
            tokens,
        ),
        image_writer=_write_debug_image,
    )

    image = np.zeros(
        (20, 30, 3),
        dtype=np.uint8,
    )

    capture.save(
        image=image,
    )
    capture.save(
        image=image,
    )

    retained_roi_paths = list(
        tmp_path.glob(
            "roi_*.png",
        )
    )

    assert len(retained_roi_paths) == 1
    assert retained_roi_paths[0] == capture.latest_path

    assert (
        unrelated_text.read_text(
            encoding="utf-8",
        )
        == "keep"
    )

    assert unrelated_image.read_bytes() == (b"keep-other-image")


@pytest.mark.parametrize(
    "max_files",
    [
        0,
        -1,
    ],
)
def test_runtime_roi_debug_capture_rejects_invalid_retention(
    tmp_path,
    max_files: int,
) -> None:

    with pytest.raises(
        ValueError,
        match="must be greater than zero",
    ):
        RuntimeRoiDebugCapture(
            directory=tmp_path,
            max_files=max_files,
        )


def test_runtime_roi_debug_capture_removes_temporary_file_when_write_fails(
    tmp_path,
) -> None:

    capture = RuntimeRoiDebugCapture(
        directory=tmp_path,
        filename_prefix="roi",
        clock=lambda: datetime(
            2026,
            8,
            3,
            21,
            3,
            14,
            tzinfo=UTC,
        ),
        token_factory=lambda: "failed",
        image_writer=lambda _path, _image: False,
    )

    image = np.zeros(
        (20, 30, 3),
        dtype=np.uint8,
    )

    with pytest.raises(
        RuntimeError,
        match="Could not save runtime ROI debug image",
    ):
        capture.save(
            image=image,
        )

    assert capture.latest_path is None
    assert (
        list(
            tmp_path.iterdir(),
        )
        == []
    )
