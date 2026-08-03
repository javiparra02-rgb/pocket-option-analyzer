from datetime import datetime

import numpy as np
import pytest

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


def test_buffer_memory_remains_bounded_during_long_session() -> None:

    buffer = FrameBuffer()

    for frame_id in range(
        1_000,
    ):
        frame = create_frame(
            frame_id=frame_id,
        )

        buffer.append(
            frame,
        )

        assert len(buffer) <= 5

    retained_frame_ids = [frame.frame_id for frame in buffer]

    assert retained_frame_ids == [
        995,
        996,
        997,
        998,
        999,
    ]

    latest_frame = buffer.latest()

    assert latest_frame is not None
    assert latest_frame.frame_id == 999


def test_buffer_clear_allows_reuse() -> None:

    buffer = FrameBuffer(
        max_size=2,
    )

    first_frame = create_frame(
        frame_id=1,
    )

    second_frame = create_frame(
        frame_id=2,
    )

    buffer.append(
        first_frame,
    )

    buffer.append(
        second_frame,
    )

    buffer.clear()

    assert len(buffer) == 0
    assert list(buffer) == []
    assert buffer.latest() is None

    reusable_frame = create_frame(
        frame_id=3,
    )

    buffer.append(
        reusable_frame,
    )

    assert len(buffer) == 1
    assert list(buffer) == [
        reusable_frame,
    ]
    assert buffer.latest() is reusable_frame


@pytest.mark.parametrize(
    "max_size",
    [
        0,
        -1,
    ],
)
def test_buffer_rejects_invalid_max_size(
    max_size: int,
) -> None:

    with pytest.raises(
        ValueError,
        match="greater than zero",
    ):
        FrameBuffer(
            max_size=max_size,
        )
