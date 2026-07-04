from pocket_option_analyzer.infrastructure.capture.services.capture_service import (
    CaptureService,
)
from pocket_option_analyzer.infrastructure.capture.services.frame_factory import FrameFactory
from pocket_option_analyzer.infrastructure.capture.services.frame_buffer import FrameBuffer
from pocket_option_analyzer.infrastructure.windows.models import Win32WindowInfo
from pocket_option_analyzer.vision.services.chart_region_extractor import ChartRegion


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
            width=100,
            height=100,
            client_left=0,
            client_top=0,
            client_width=100,
            client_height=100,
            visible=True,
            minimized=False,
        )


class FakeRegionExtractor:
    def extract(self, window):
        return ChartRegion(
            left=0,
            top=0,
            width=100,
            height=100,
        )


class FakeCapture:
    def capture(self, region):
        import numpy as np
        return np.zeros((10, 10, 3), dtype=np.uint8)


def test_capture_once_returns_frame():
    service = CaptureService(
        finder=FakeFinder(),
        reader=FakeReader(),
        region_extractor=FakeRegionExtractor(),
        capture=FakeCapture(),
        frame_factory=FrameFactory(),
        frame_buffer=FrameBuffer(),
    )

    frame = service.capture_once("Pocket Option")

    assert frame is not None