import numpy as np
import pytest

from pocket_option_analyzer.vision import VisionPipeline


def test_pipeline_converts_bgra_to_bgr() -> None:
    image = np.zeros((100, 100, 4), dtype=np.uint8)

    pipeline = VisionPipeline()

    result = pipeline.process(image)

    assert result.shape == (100, 100, 3)


def test_pipeline_extracts_independent_roi() -> None:

    image = np.arange(
        200 * 300 * 3,
        dtype=np.uint8,
    ).reshape(
        200,
        300,
        3,
    )

    expected = image[
        30:70,
        20:100,
    ].copy()

    pipeline = VisionPipeline()

    result = pipeline.process(
        image=image,
        roi=(
            20,
            30,
            80,
            40,
        ),
    )

    assert result.shape == (
        40,
        80,
        3,
    )

    assert result.flags.c_contiguous is True

    assert not np.shares_memory(
        result,
        image,
    )

    assert np.array_equal(
        result,
        expected,
    )

    image.fill(
        0,
    )

    assert np.array_equal(
        result,
        expected,
    )


@pytest.mark.parametrize(
    "roi",
    [
        (
            -1,
            10,
            20,
            20,
        ),
        (
            90,
            10,
            20,
            20,
        ),
    ],
    ids=[
        "negative_origin",
        "outside_bounds",
    ],
)
def test_pipeline_rejects_invalid_roi(
    roi: tuple[int, int, int, int],
) -> None:

    image = np.zeros(
        (
            100,
            100,
            4,
        ),
        dtype=np.uint8,
    )

    pipeline = VisionPipeline()

    with pytest.raises(
        ValueError,
        match="ROI",
    ):
        pipeline.process(
            image=image,
            roi=roi,
        )


def test_pipeline_rejects_unsupported_pixel_dtype() -> None:

    image = np.zeros(
        (
            100,
            100,
            3,
        ),
        dtype=np.float32,
    )

    pipeline = VisionPipeline()

    with pytest.raises(
        ValueError,
        match="Invalid image",
    ):
        pipeline.process(
            image,
        )
