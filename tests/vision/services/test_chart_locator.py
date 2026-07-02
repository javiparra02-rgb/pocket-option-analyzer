import numpy as np

from pocket_option_analyzer.vision.models import ChartRegion
from pocket_option_analyzer.vision.services import ChartLocator


def test_chart_locator_returns_region() -> None:
    image = np.zeros((600, 800, 3), dtype=np.uint8)

    expected = ChartRegion(
        x=100,
        y=50,
        width=500,
        height=300,
    )

    locator = ChartLocator(expected)

    assert locator.locate(image) == expected