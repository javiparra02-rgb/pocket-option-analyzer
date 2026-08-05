import numpy as np
import pytest

from pocket_option_analyzer.vision.preprocessing import (
    RegionExtractor,
)


def test_extract_region_returns_independent_contiguous_copy() -> None:

    image = np.arange(
        100 * 200 * 3,
        dtype=np.uint8,
    ).reshape(
        100,
        200,
        3,
    )

    expected = image[
        10:60,
        20:100,
    ].copy()

    roi = RegionExtractor.extract(
        image=image,
        x=20,
        y=10,
        width=80,
        height=50,
    )

    assert roi.shape == (
        50,
        80,
        3,
    )

    assert roi.flags.c_contiguous is True

    assert not np.shares_memory(
        roi,
        image,
    )

    assert np.array_equal(
        roi,
        expected,
    )

    image.fill(
        0,
    )

    assert np.array_equal(
        roi,
        expected,
    )


def test_extract_region_accepts_exact_image_boundary() -> None:

    image = np.zeros(
        (
            100,
            200,
            3,
        ),
        dtype=np.uint8,
    )

    roi = RegionExtractor.extract(
        image=image,
        x=120,
        y=50,
        width=80,
        height=50,
    )

    assert roi.shape == (
        50,
        80,
        3,
    )


@pytest.mark.parametrize(
    (
        "x",
        "y",
    ),
    [
        (
            -1,
            0,
        ),
        (
            0,
            -1,
        ),
    ],
)
def test_extract_region_rejects_negative_coordinates(
    x: int,
    y: int,
) -> None:

    image = np.zeros(
        (
            100,
            200,
            3,
        ),
        dtype=np.uint8,
    )

    with pytest.raises(
        ValueError,
        match="coordinates cannot be negative",
    ):
        RegionExtractor.extract(
            image=image,
            x=x,
            y=y,
            width=20,
            height=20,
        )


@pytest.mark.parametrize(
    (
        "width",
        "height",
    ),
    [
        (
            0,
            20,
        ),
        (
            -1,
            20,
        ),
        (
            20,
            0,
        ),
        (
            20,
            -1,
        ),
    ],
)
def test_extract_region_rejects_non_positive_dimensions(
    width: int,
    height: int,
) -> None:

    image = np.zeros(
        (
            100,
            200,
            3,
        ),
        dtype=np.uint8,
    )

    with pytest.raises(
        ValueError,
        match="dimensions must be greater than zero",
    ):
        RegionExtractor.extract(
            image=image,
            x=10,
            y=10,
            width=width,
            height=height,
        )


@pytest.mark.parametrize(
    (
        "x",
        "y",
        "width",
        "height",
    ),
    [
        (
            150,
            10,
            60,
            20,
        ),
        (
            10,
            80,
            20,
            30,
        ),
    ],
)
def test_extract_region_rejects_out_of_bounds_region(
    x: int,
    y: int,
    width: int,
    height: int,
) -> None:

    image = np.zeros(
        (
            100,
            200,
            3,
        ),
        dtype=np.uint8,
    )

    with pytest.raises(
        ValueError,
        match="fit entirely within image bounds",
    ):
        RegionExtractor.extract(
            image=image,
            x=x,
            y=y,
            width=width,
            height=height,
        )


def test_extract_region_rejects_image_without_spatial_dimensions() -> None:

    image = np.zeros(
        (100,),
        dtype=np.uint8,
    )

    with pytest.raises(
        ValueError,
        match="at least two dimensions",
    ):
        RegionExtractor.extract(
            image=image,
            x=0,
            y=0,
            width=10,
            height=10,
        )
