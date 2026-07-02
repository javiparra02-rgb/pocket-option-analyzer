import numpy as np

from pocket_option_analyzer.vision.preprocessing import ImageConverter


def test_bgra_to_bgr() -> None:
    image = np.zeros((20, 20, 4), dtype=np.uint8)

    converted = ImageConverter.bgra_to_bgr(image)

    assert converted.shape == (20, 20, 3)