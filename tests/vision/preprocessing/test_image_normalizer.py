import numpy as np

from pocket_option_analyzer.vision.preprocessing.image_normalizer import (
    ImageNormalizer,
)


def test_normalize_returns_image():

    image = np.zeros(
        (100, 100, 3),
        dtype=np.uint8,
    )

    normalizer = ImageNormalizer()

    result = normalizer.normalize(image)

    assert result.shape == image.shape