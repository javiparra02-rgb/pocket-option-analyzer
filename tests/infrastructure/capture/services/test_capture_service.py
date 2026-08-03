import numpy as np

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

    def capture(
        self,
        window,
    ) -> np.ndarray:
        return self.image


class FakeRegionExtractor:
    def extract(self, image):
        return ChartRegion(
            x=20,
            y=20,
            width=100,
            height=100,
        )


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
