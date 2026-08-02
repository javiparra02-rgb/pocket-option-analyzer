import numpy as np

from pocket_option_analyzer.infrastructure.capture.services import (
    CaptureService,
    FrameBuffer,
    FrameFactory,
)
from pocket_option_analyzer.infrastructure.windows.models import (
    Win32WindowInfo,
)
from pocket_option_analyzer.vision.models import ChartRegion


class FakeFinder:
    def find(self, title):
        return Win32WindowInfo(
            hwnd=1,
            title=title,
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


class FakeReader:
    def read(self, hwnd):
        return FakeFinder().find("Pocket Option")


class FakeCapture:
    def capture(self, window):
        return np.zeros((200, 200, 3), dtype=np.uint8)


class FakeExtractor:
    def extract(self, image):
        return ChartRegion(
            x=20,
            y=20,
            width=100,
            height=100,
        )


class FakeDataset:
    def __init__(self):
        self.called = False

    def save(self, image):
        self.called = True


def test_dataset_service_is_called():

    dataset = FakeDataset()

    service = CaptureService(
        finder=FakeFinder(),
        reader=FakeReader(),
        capture=FakeCapture(),
        region_extractor=FakeExtractor(),
        frame_factory=FrameFactory(),
        frame_buffer=FrameBuffer(),
        dataset_capture=dataset,
    )

    service.capture_once()

    assert dataset.called
