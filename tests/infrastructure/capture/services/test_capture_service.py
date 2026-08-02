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
    def capture(self, window):
        return np.zeros(
            (200, 200, 3),
            dtype=np.uint8,
        )


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
