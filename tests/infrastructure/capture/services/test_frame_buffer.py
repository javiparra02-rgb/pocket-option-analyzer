from datetime import datetime

import numpy as np

from pocket_option_analyzer.infrastructure.capture.models import Frame
from pocket_option_analyzer.infrastructure.capture.services import FrameBuffer


def create_frame(frame_id: int) -> Frame:
    return Frame(
        frame_id=frame_id,
        timestamp=datetime.now(),
        image=np.zeros((10, 10, 4), dtype=np.uint8),
    )


def test_buffer_keeps_latest_frames() -> None:
    buffer = FrameBuffer(max_size=3)

    buffer.append(create_frame(1))
    buffer.append(create_frame(2))
    buffer.append(create_frame(3))
    buffer.append(create_frame(4))

    assert len(buffer) == 3

    ids = [frame.frame_id for frame in buffer]

    assert ids == [2, 3, 4]


def test_latest_returns_last_frame() -> None:
    buffer = FrameBuffer()

    assert buffer.latest() is None

    frame = create_frame(1)

    buffer.append(frame)

    assert buffer.latest() == frame


def test_clear_empties_buffer() -> None:
    buffer = FrameBuffer()

    buffer.append(create_frame(1))

    buffer.clear()

    assert len(buffer) == 0
    assert buffer.latest() is None