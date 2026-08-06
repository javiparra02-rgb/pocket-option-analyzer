from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np
import pytest

from pocket_option_analyzer.domain.signals import (
    SignalDirection,
    SignalHistory,
)
from pocket_option_analyzer.infrastructure.bootstrap import (
    PocketOptionRuntimeFactory,
    RuntimeWindowFinder,
    RuntimeWindowHandle,
    RuntimeWindowInfo,
    RuntimeWindowReader,
)
from pocket_option_analyzer.infrastructure.capture import (
    CaptureUnavailableError,
)
from pocket_option_analyzer.vision.models import ChartRegion
from pocket_option_analyzer.vision.services import (
    ChartRegionExtractor,
    FixedChartRegionExtractor,
    PocketOptionChartRegionExtractor,
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


def _runtime_window_info(
    **overrides,
) -> RuntimeWindowInfo:

    values = {
        "hwnd": 123,
        "title": "Pocket Option",
        "left": 10,
        "top": 20,
        "width": 300,
        "height": 200,
        "visible": True,
        "minimized": False,
    }

    values.update(
        overrides,
    )

    return RuntimeWindowInfo(
        **values,
    )


def test_runtime_window_reader_returns_window_info_from_provider() -> None:

    expected = _runtime_window_info()

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
    assert result.is_capture_candidate is True


@pytest.mark.parametrize(
    "hwnd",
    [
        0,
        -1,
    ],
)
def test_runtime_window_reader_rejects_invalid_requested_handle(
    hwnd: int,
) -> None:

    provider_called = False

    def info_provider(
        requested_hwnd: int,
    ) -> RuntimeWindowInfo:
        nonlocal provider_called

        provider_called = True

        return _runtime_window_info(
            hwnd=requested_hwnd,
        )

    reader = RuntimeWindowReader(
        info_provider=info_provider,
    )

    with pytest.raises(
        ValueError,
        match="must be greater than zero",
    ):
        reader.read(
            hwnd=hwnd,
        )

    assert provider_called is False


def test_runtime_window_reader_rejects_unexpected_returned_handle() -> None:

    reader = RuntimeWindowReader(
        info_provider=lambda hwnd: _runtime_window_info(
            hwnd=999,
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="unexpected handle",
    ):
        reader.read(
            hwnd=123,
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {
            "title": "   ",
        },
        {
            "width": 0,
        },
        {
            "height": -1,
        },
        {
            "visible": False,
        },
        {
            "minimized": True,
        },
    ],
)
def test_runtime_window_reader_rejects_non_capturable_information(
    overrides: dict[str, object],
) -> None:

    reader = RuntimeWindowReader(
        info_provider=lambda hwnd: _runtime_window_info(
            hwnd=hwnd,
            **overrides,
        ),
    )

    with pytest.raises(
        CaptureUnavailableError,
        match="not available for capture",
    ):
        reader.read(
            hwnd=123,
        )


def test_runtime_window_reader_accepts_negative_screen_coordinates() -> None:

    expected = _runtime_window_info(
        left=-1920,
        top=-120,
        width=1600,
        height=900,
    )

    reader = RuntimeWindowReader(
        info_provider=lambda hwnd: expected,
    )

    result = reader.read(
        hwnd=123,
    )

    assert result is expected
    assert result.left == -1920
    assert result.top == -120
    assert result.right == -320
    assert result.bottom == 780
    assert result.area == 1_440_000
    assert result.is_capture_candidate is True


def test_fixed_chart_region_extractor_preserves_configured_region() -> None:

    configured_region = ChartRegion(
        x=10,
        y=20,
        width=500,
        height=400,
    )

    extractor = FixedChartRegionExtractor(
        region=configured_region,
    )

    image = np.zeros(
        (
            100,
            200,
            3,
        ),
        dtype=np.uint8,
    )

    result = extractor.extract(
        image=image,
    )

    assert result is configured_region
    assert result.x == 10
    assert result.y == 20
    assert result.width == 500
    assert result.height == 400

    assert not result.fits_within(
        image_width=200,
        image_height=100,
    )


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
    assert region.bottom == 765

    assert region.fits_within(
        image_width=1600,
        image_height=900,
    )


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


@pytest.mark.parametrize(
    "region",
    [
        ChartRegion(
            x=-1,
            y=0,
            width=100,
            height=100,
        ),
        ChartRegion(
            x=0,
            y=-1,
            width=100,
            height=100,
        ),
        ChartRegion(
            x=0,
            y=0,
            width=0,
            height=100,
        ),
        ChartRegion(
            x=0,
            y=0,
            width=100,
            height=0,
        ),
    ],
    ids=[
        "negative_x",
        "negative_y",
        "zero_width",
        "zero_height",
    ],
)
def test_fixed_chart_region_extractor_rejects_invalid_configuration(
    region: ChartRegion,
) -> None:

    with pytest.raises(
        ValueError,
        match="Fixed chart region",
    ):
        FixedChartRegionExtractor(
            region=region,
        )


@pytest.mark.parametrize(
    (
        "top_ratio",
        "right_ratio",
        "bottom_ratio",
        "expected_message",
    ),
    [
        (
            -0.01,
            0.14,
            0.15,
            "top_ratio",
        ),
        (
            1.0,
            0.14,
            0.15,
            "top_ratio",
        ),
        (
            0.10,
            -0.01,
            0.15,
            "right_ratio",
        ),
        (
            0.10,
            1.0,
            0.15,
            "right_ratio",
        ),
        (
            0.10,
            0.14,
            -0.01,
            "bottom_ratio",
        ),
        (
            0.10,
            0.14,
            1.0,
            "bottom_ratio",
        ),
        (
            float("nan"),
            0.14,
            0.15,
            "top_ratio",
        ),
        (
            0.10,
            float("inf"),
            0.15,
            "right_ratio",
        ),
    ],
    ids=[
        "negative_top",
        "full_top",
        "negative_right",
        "full_right",
        "negative_bottom",
        "full_bottom",
        "nan_top",
        "infinite_right",
    ],
)
def test_pocket_option_chart_region_extractor_rejects_invalid_ratio(
    top_ratio: float,
    right_ratio: float,
    bottom_ratio: float,
    expected_message: str,
) -> None:

    with pytest.raises(
        ValueError,
        match=expected_message,
    ):
        PocketOptionChartRegionExtractor(
            top_ratio=top_ratio,
            right_ratio=right_ratio,
            bottom_ratio=bottom_ratio,
        )


@pytest.mark.parametrize(
    (
        "top_ratio",
        "bottom_ratio",
    ),
    [
        (
            0.50,
            0.50,
        ),
        (
            0.75,
            0.30,
        ),
    ],
    ids=[
        "exact_full_height",
        "exceeds_full_height",
    ],
)
def test_pocket_option_chart_region_extractor_rejects_vertical_ratio_sum(
    top_ratio: float,
    bottom_ratio: float,
) -> None:

    with pytest.raises(
        ValueError,
        match="sum to less than one",
    ):
        PocketOptionChartRegionExtractor(
            top_ratio=top_ratio,
            bottom_ratio=bottom_ratio,
        )


def test_pocket_option_chart_region_extractor_accepts_zero_ratios() -> None:

    extractor = PocketOptionChartRegionExtractor(
        top_ratio=0.0,
        right_ratio=0.0,
        bottom_ratio=0.0,
    )

    image = np.zeros(
        (
            100,
            200,
            3,
        ),
        dtype=np.uint8,
    )

    result = extractor.extract(
        image=image,
    )

    assert result == ChartRegion(
        x=0,
        y=0,
        width=200,
        height=100,
    )

    assert result.fits_within(
        image_width=200,
        image_height=100,
    )


@pytest.mark.parametrize(
    "extractor",
    [
        FixedChartRegionExtractor(
            region=ChartRegion(
                x=0,
                y=0,
                width=100,
                height=100,
            )
        ),
        PocketOptionChartRegionExtractor(),
    ],
    ids=[
        "fixed_region",
        "pocket_option_region",
    ],
)
@pytest.mark.parametrize(
    "image",
    [
        np.empty(
            (
                0,
                100,
                3,
            ),
            dtype=np.uint8,
        ),
        np.empty(
            (
                100,
                0,
                4,
            ),
            dtype=np.uint8,
        ),
        np.zeros(
            (
                100,
                100,
            ),
            dtype=np.uint8,
        ),
        np.zeros(
            (
                100,
                100,
                2,
            ),
            dtype=np.uint8,
        ),
        np.zeros(
            (
                100,
                100,
                3,
            ),
            dtype=np.float32,
        ),
    ],
    ids=[
        "zero_height",
        "zero_width",
        "two_dimensions",
        "unsupported_channels",
        "unsupported_dtype",
    ],
)
def test_chart_region_extractors_reject_invalid_images(
    extractor: ChartRegionExtractor,
    image: np.ndarray,
) -> None:

    with pytest.raises(
        ValueError,
        match="valid uint8 BGR or BGRA image",
    ):
        extractor.extract(
            image=image,
        )
