import numpy as np

from pocket_option_analyzer.infrastructure.capture.models import WindowInfo
from pocket_option_analyzer.infrastructure.capture.services import (
    CaptureService,
    FrameBuffer,
    FrameFactory,
)


class FakeLocator:
    def find(self, title: str):
        return WindowInfo(
            title=title,
            left=0,
            top=0,
            width=50,
            height=50,
        )


class FakeCapture:
    def capture(self, window):
        return np.zeros((50, 50, 4), dtype=np.uint8)


def test_capture_once_returns_frame() -> None:
    service = CaptureService(
        locator=FakeLocator(),
        capture=FakeCapture(),
        frame_factory=FrameFactory(),
        frame_buffer=FrameBuffer(),
    )

    frame = service.capture_once()

    assert frame is not None
    assert frame.frame_id == 1
    assert service.latest_frame() == frame