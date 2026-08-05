import numpy as np

from pocket_option_analyzer.vision.models import ChartRegion
from pocket_option_analyzer.vision.services.roi_debug_renderer import (
    RoiDebugRenderer,
)


def test_render_returns_independent_image() -> None:

    image = np.zeros(
        (
            300,
            400,
            3,
        ),
        dtype=np.uint8,
    )

    region = ChartRegion(
        x=50,
        y=60,
        width=200,
        height=100,
    )

    renderer = RoiDebugRenderer()

    result = renderer.render(
        image,
        region,
    )

    assert result.shape == image.shape

    assert result.dtype == image.dtype

    assert not np.shares_memory(
        result,
        image,
    )

    assert np.any(
        result != image,
    )
