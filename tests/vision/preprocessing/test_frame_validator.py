import numpy as np

from pocket_option_analyzer.vision.preprocessing import FrameValidator


def test_valid_image() -> None:
    image = np.zeros((100, 100, 4), dtype=np.uint8)

    assert FrameValidator.validate(image)


def test_none_image() -> None:
    assert not FrameValidator.validate(None)


def test_invalid_dimensions() -> None:
    image = np.zeros((100, 100), dtype=np.uint8)

    assert not FrameValidator.validate(image)


def test_invalid_channels() -> None:
    image = np.zeros((100, 100, 2), dtype=np.uint8)

    assert not FrameValidator.validate(image)
