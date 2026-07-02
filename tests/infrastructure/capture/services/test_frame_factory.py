import numpy as np

from pocket_option_analyzer.infrastructure.capture import FrameFactory


def test_frame_factory_generates_incremental_ids() -> None:
    factory = FrameFactory()

    image = np.zeros((10, 10, 4), dtype=np.uint8)

    frame1 = factory.create(image)
    frame2 = factory.create(image)

    assert frame1.frame_id == 1
    assert frame2.frame_id == 2

    assert frame2.frame_id > frame1.frame_id