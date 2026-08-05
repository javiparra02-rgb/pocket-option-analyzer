import numpy as np
import pytest

from pocket_option_analyzer.vision import VisionPipeline


def test_pipeline_converts_bgra_to_bgr() -> None:
    image = np.zeros((100, 100, 4), dtype=np.uint8)

    pipeline = VisionPipeline()

    result = pipeline.process(image)

    assert result.shape == (100, 100, 3)


def test_pipeline_extracts_roi() -> None:
    image = np.zeros((200, 300, 4), dtype=np.uint8)

    pipeline = VisionPipeline()

    result = pipeline.process(
        image=image,
        roi=(20, 30, 80, 40),
    )

    assert result.shape == (40, 80, 3)


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
