import numpy as np
import pytest

from pocket_option_analyzer.infrastructure.capture import (
    CaptureUnavailableError,
)
from pocket_option_analyzer.infrastructure.capture.services.capture_service import (
    CaptureService,
)
from pocket_option_analyzer.infrastructure.capture.services.frame_buffer import (
    FrameBuffer,
)
from pocket_option_analyzer.infrastructure.capture.services.frame_factory import (
    FrameFactory,
)
from pocket_option_analyzer.infrastructure.windows.models import (
    Win32WindowInfo,
)
from pocket_option_analyzer.vision.models import (
    ChartRegion,
)
from pocket_option_analyzer.vision.services import (
    FixedChartRegionExtractor,
    PocketOptionPriceObservationRegionExtractor,
)


class FakeFinder:
    def find(self, title: str):
        class W:
            hwnd = 123

        return W()


class FakeReader:
    def read(self, hwnd: int):
        return Win32WindowInfo(
            hwnd=hwnd,
            title="Pocket Option",
            left=0,
            top=0,
            width=200,
            height=200,
            client_left=0,
            client_top=0,
            client_width=200,
            client_height=200,
            visible=True,
            minimized=False,
        )


class FailingReader:
    def __init__(
        self,
        error: Exception,
    ) -> None:
        self._error = error

    def read(
        self,
        hwnd: int,
    ):
        del hwnd

        raise self._error


class FakeCapture:
    def __init__(
        self,
        image: np.ndarray | None = None,
    ) -> None:
        self.image = (
            image
            if image is not None
            else np.zeros(
                (200, 200, 3),
                dtype=np.uint8,
            )
        )
        self.capture_calls = 0

    def capture(
        self,
        window,
    ) -> np.ndarray:
        self.capture_calls += 1

        return self.image


class FakeRegionExtractor:
    def __init__(
        self,
        region: ChartRegion | None = None,
    ) -> None:
        self._region = (
            region
            if region is not None
            else ChartRegion(
                x=20,
                y=20,
                width=100,
                height=100,
            )
        )

        self.extract_calls = 0
        self.received_images: list[np.ndarray] = []

    def extract(
        self,
        image,
    ) -> ChartRegion:
        self.extract_calls += 1
        self.received_images.append(image)

        return self._region


def test_capture_once_returns_frame():

    service = CaptureService(
        finder=FakeFinder(),
        reader=FakeReader(),
        capture=FakeCapture(),
        region_extractor=FakeRegionExtractor(),
        frame_factory=FrameFactory(),
        frame_buffer=FrameBuffer(),
    )

    frame = service.capture_once()

    assert frame is not None


def test_capture_once_detaches_roi_from_full_capture() -> None:

    source_image = np.arange(
        200 * 200 * 3,
        dtype=np.uint8,
    ).reshape(
        200,
        200,
        3,
    )

    expected_roi = source_image[
        20:120,
        20:120,
    ].copy()

    capture = FakeCapture(
        image=source_image,
    )

    frame_buffer = FrameBuffer()

    service = CaptureService(
        finder=FakeFinder(),
        reader=FakeReader(),
        capture=capture,
        region_extractor=FakeRegionExtractor(),
        frame_factory=FrameFactory(),
        frame_buffer=frame_buffer,
    )

    frame = service.capture_once()

    assert frame is not None

    assert frame.image.shape == (
        100,
        100,
        3,
    )

    assert frame.image.flags.c_contiguous is True

    assert not np.shares_memory(
        frame.image,
        source_image,
    )

    assert np.array_equal(
        frame.image,
        expected_roi,
    )

    source_image.fill(
        0,
    )

    assert np.array_equal(
        frame.image,
        expected_roi,
    )

    assert frame_buffer.latest() is frame


def test_capture_once_derives_independent_rois_from_one_capture() -> None:
    source_image = np.arange(
        200 * 200 * 3,
        dtype=np.uint8,
    ).reshape(200, 200, 3)
    expected_chart_roi = source_image[20:120, 20:120].copy()
    expected_price_roi = source_image[60:160, 60:160].copy()
    capture = FakeCapture(image=source_image)
    chart_region = ChartRegion(x=20, y=20, width=100, height=100)
    price_region = ChartRegion(x=60, y=60, width=100, height=100)
    chart_extractor = FakeRegionExtractor(region=chart_region)
    price_extractor = FakeRegionExtractor(region=price_region)

    service = CaptureService(
        finder=FakeFinder(),
        reader=FakeReader(),
        capture=capture,
        region_extractor=chart_extractor,
        frame_factory=FrameFactory(),
        frame_buffer=FrameBuffer(),
        price_observation_region_extractor=price_extractor,
    )

    frame = service.capture_once()

    assert frame is not None
    assert frame.price_observation_image is not None
    assert capture.capture_calls == 1
    assert chart_extractor.received_images == [source_image]
    assert price_extractor.received_images == [source_image]
    assert frame.image.flags.c_contiguous is True
    assert frame.price_observation_image.flags.c_contiguous is True
    assert not np.shares_memory(frame.image, source_image)
    assert not np.shares_memory(frame.price_observation_image, source_image)
    assert not np.shares_memory(frame.image, frame.price_observation_image)
    assert np.array_equal(frame.image, expected_chart_roi)
    assert np.array_equal(frame.price_observation_image, expected_price_roi)
    assert frame.chart_region is chart_region
    assert frame.price_observation_region is price_region
    assert frame.chart_region.width == frame.price_observation_region.width
    assert frame.chart_region.height == frame.price_observation_region.height
    assert frame.chart_region.y != frame.price_observation_region.y

    source_image.fill(0)

    assert np.array_equal(frame.image, expected_chart_roi)
    assert np.array_equal(
        frame.price_observation_image,
        expected_price_roi,
    )


def test_capture_once_without_price_extractor_keeps_optional_image_none() -> None:
    service = CaptureService(
        finder=FakeFinder(),
        reader=FakeReader(),
        capture=FakeCapture(),
        region_extractor=FakeRegionExtractor(),
        frame_factory=FrameFactory(),
        frame_buffer=FrameBuffer(),
    )

    frame = service.capture_once()

    assert frame is not None
    assert frame.price_observation_image is None
    assert frame.chart_region is not None
    assert frame.price_observation_region is None


def test_capture_once_preserves_fixed_chart_and_proportional_price_regions() -> None:
    source_image = np.zeros((200, 200, 3), dtype=np.uint8)
    chart_region = ChartRegion(x=15, y=35, width=120, height=90)
    price_extractor = PocketOptionPriceObservationRegionExtractor()
    expected_price_region = price_extractor.extract(source_image)
    service = CaptureService(
        finder=FakeFinder(),
        reader=FakeReader(),
        capture=FakeCapture(image=source_image),
        region_extractor=FixedChartRegionExtractor(chart_region),
        frame_factory=FrameFactory(),
        frame_buffer=FrameBuffer(),
        price_observation_region_extractor=price_extractor,
    )

    frame = service.capture_once()

    assert frame is not None
    assert frame.chart_region is chart_region
    assert frame.price_observation_region == expected_price_region
    assert frame.chart_region != frame.price_observation_region


def test_capture_once_rejects_price_region_outside_capture_bounds() -> None:
    frame_buffer = FrameBuffer()
    service = CaptureService(
        finder=FakeFinder(),
        reader=FakeReader(),
        capture=FakeCapture(),
        region_extractor=FakeRegionExtractor(),
        frame_factory=FrameFactory(),
        frame_buffer=frame_buffer,
        price_observation_region_extractor=FakeRegionExtractor(
            region=ChartRegion(x=150, y=20, width=100, height=100)
        ),
    )

    result = service.capture_once()

    assert result is None
    assert frame_buffer.latest() is None


def test_capture_once_returns_none_when_window_is_temporarily_unavailable() -> None:

    capture = FakeCapture()
    frame_buffer = FrameBuffer()

    existing_frame = FrameFactory().create(
        np.zeros(
            (10, 10, 3),
            dtype=np.uint8,
        )
    )

    frame_buffer.append(
        existing_frame,
    )

    service = CaptureService(
        finder=FakeFinder(),
        reader=FailingReader(CaptureUnavailableError("Window was minimized.")),
        capture=capture,
        region_extractor=FakeRegionExtractor(),
        frame_factory=FrameFactory(),
        frame_buffer=frame_buffer,
    )

    result = service.capture_once()

    assert result is None
    assert capture.capture_calls == 0
    assert frame_buffer.latest() is existing_frame


def test_capture_once_propagates_unexpected_reader_error() -> None:

    capture = FakeCapture()

    service = CaptureService(
        finder=FakeFinder(),
        reader=FailingReader(RuntimeError("Unexpected reader failure.")),
        capture=capture,
        region_extractor=FakeRegionExtractor(),
        frame_factory=FrameFactory(),
        frame_buffer=FrameBuffer(),
    )

    with pytest.raises(
        RuntimeError,
        match="Unexpected reader failure",
    ):
        service.capture_once()

    assert capture.capture_calls == 0


def test_capture_once_returns_none_for_empty_capture() -> None:

    extractor = FakeRegionExtractor()
    frame_buffer = FrameBuffer()

    existing_frame = FrameFactory().create(
        np.zeros(
            (10, 10, 3),
            dtype=np.uint8,
        )
    )

    frame_buffer.append(
        existing_frame,
    )

    service = CaptureService(
        finder=FakeFinder(),
        reader=FakeReader(),
        capture=FakeCapture(
            image=np.empty(
                (0, 0, 4),
                dtype=np.uint8,
            )
        ),
        region_extractor=extractor,
        frame_factory=FrameFactory(),
        frame_buffer=frame_buffer,
    )

    result = service.capture_once()

    assert result is None
    assert extractor.extract_calls == 0
    assert frame_buffer.latest() is existing_frame


def test_capture_once_returns_none_for_empty_chart_region() -> None:

    extractor = FakeRegionExtractor(
        region=ChartRegion(
            x=20,
            y=20,
            width=0,
            height=100,
        )
    )

    frame_buffer = FrameBuffer()

    service = CaptureService(
        finder=FakeFinder(),
        reader=FakeReader(),
        capture=FakeCapture(),
        region_extractor=extractor,
        frame_factory=FrameFactory(),
        frame_buffer=frame_buffer,
    )

    result = service.capture_once()

    assert result is None
    assert extractor.extract_calls == 1
    assert frame_buffer.latest() is None


def test_capture_once_rejects_regions_outside_capture_bounds() -> None:

    invalid_regions = (
        ChartRegion(
            x=-1,
            y=20,
            width=100,
            height=100,
        ),
        ChartRegion(
            x=150,
            y=20,
            width=100,
            height=100,
        ),
        ChartRegion(
            x=20,
            y=150,
            width=100,
            height=100,
        ),
    )

    for invalid_region in invalid_regions:
        frame_buffer = FrameBuffer()

        service = CaptureService(
            finder=FakeFinder(),
            reader=FakeReader(),
            capture=FakeCapture(),
            region_extractor=FakeRegionExtractor(
                region=invalid_region,
            ),
            frame_factory=FrameFactory(),
            frame_buffer=frame_buffer,
        )

        result = service.capture_once()

        assert result is None
        assert frame_buffer.latest() is None


@pytest.mark.parametrize(
    "image",
    [
        np.zeros(
            (
                200,
                200,
            ),
            dtype=np.uint8,
        ),
        np.zeros(
            (
                200,
                200,
                3,
            ),
            dtype=np.float32,
        ),
    ],
    ids=[
        "invalid_dimensions",
        "unsupported_dtype",
    ],
)
def test_capture_once_rejects_unsupported_capture_format(
    image: np.ndarray,
) -> None:

    extractor = FakeRegionExtractor()

    service = CaptureService(
        finder=FakeFinder(),
        reader=FakeReader(),
        capture=FakeCapture(
            image=image,
        ),
        region_extractor=extractor,
        frame_factory=FrameFactory(),
        frame_buffer=FrameBuffer(),
    )

    with pytest.raises(
        ValueError,
        match="unsupported image format",
    ):
        service.capture_once()

    assert extractor.extract_calls == 0
