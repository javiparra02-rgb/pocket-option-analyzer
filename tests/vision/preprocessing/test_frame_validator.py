import numpy as np
import pytest

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


def test_non_array_image() -> None:

    assert not FrameValidator.validate(
        object(),
    )


@pytest.mark.parametrize(
    "shape",
    [
        (
            0,
            100,
            3,
        ),
        (
            100,
            0,
            4,
        ),
    ],
)
def test_empty_spatial_dimensions(
    shape: tuple[int, int, int],
) -> None:

    image = np.zeros(
        shape,
        dtype=np.uint8,
    )

    assert not FrameValidator.validate(
        image,
    )


@pytest.mark.parametrize(
    "dtype",
    [
        np.uint16,
        np.int16,
        np.float32,
        np.bool_,
    ],
)
def test_unsupported_pixel_dtype(
    dtype,
) -> None:

    image = np.zeros(
        (
            100,
            100,
            3,
        ),
        dtype=dtype,
    )

    assert not FrameValidator.validate(
        image,
    )


def test_valid_non_contiguous_uint8_view() -> None:

    source = np.zeros(
        (
            100,
            200,
            3,
        ),
        dtype=np.uint8,
    )

    image = source[
        :,
        ::2,
        :,
    ]

    assert image.flags.c_contiguous is False

    assert FrameValidator.validate(
        image,
    )
