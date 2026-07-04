import numpy as np

from pocket_option_analyzer.vision.preprocessing import (
    ColorMask,
)


def test_create_mask():

    hsv = np.zeros(
        (100, 100, 3),
        dtype=np.uint8,
    )

    mask = ColorMask().create(
        hsv,
        (0, 0, 0),
        (255, 255, 255),
    )

    assert mask.shape == (100, 100)