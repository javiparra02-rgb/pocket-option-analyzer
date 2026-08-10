from datetime import datetime

import numpy as np

from pocket_option_analyzer.infrastructure.capture.models import Frame


def test_frame_dimensions() -> None:
    image = np.zeros((720, 1280, 3), dtype=np.uint8)

    frame = Frame(
        frame_id=1,
        timestamp=datetime.now(),
        image=image,
    )

    assert frame.width == 1280
    assert frame.height == 720
    assert frame.channels == 3
    assert frame.price_observation_image is None


def test_frame_accepts_price_observation_image() -> None:
    image = np.zeros((720, 1280, 3), dtype=np.uint8)
    price_observation_image = np.ones((800, 1280, 3), dtype=np.uint8)

    frame = Frame(
        frame_id=1,
        timestamp=datetime.now(),
        image=image,
        price_observation_image=price_observation_image,
    )

    assert frame.image is image
    assert frame.price_observation_image is price_observation_image
    assert frame.width == 1280
    assert frame.height == 720
    assert frame.channels == 3
