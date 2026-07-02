from datetime import datetime

import numpy as np

from pocket_option_analyzer.infrastructure.capture import (
    PocketOptionFrameProvider,
)
from pocket_option_analyzer.infrastructure.capture.models import (
    Frame,
    WindowInfo,
)


class FakeLocator:
    def find(self, window_title: str):
        return WindowInfo(
            title=window_title,
            left=0,
            top=0,
            width=100,
            height=100,
        )


class FakeCapture:
    def capture(self, window):
        return np.zeros((100, 100, 4), dtype=np.uint8)


def test_frame_provider() -> None:
    provider = PocketOptionFrameProvider(
        locator=FakeLocator(),
        capture=FakeCapture(),
    )

    frame = provider.get_frame()

    assert frame is not None
    assert frame.frame_id == 1
    assert frame.width == 100
    assert frame.height == 100