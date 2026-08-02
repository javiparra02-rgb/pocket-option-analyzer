import numpy as np

from pocket_option_analyzer.vision.services.chart_region_extractor import (
    ChartRegion,
)
from pocket_option_analyzer.vision.services.roi_debug_renderer import (
    RoiDebugRenderer,
)


def test_render_returns_image():

    image = np.zeros((300, 400, 3), dtype=np.uint8)

    region = ChartRegion(
        left=50,
        top=60,
        width=200,
        height=100,
    )

    renderer = RoiDebugRenderer()

    result = renderer.render(image, region)

    assert result.shape == image.shape
