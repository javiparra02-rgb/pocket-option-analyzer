import numpy as np
import pytest

from pocket_option_analyzer.vision.models import ChartRegion
from pocket_option_analyzer.vision.services import (
    ChartRegionExtractor,
    FixedChartRegionExtractor,
    PocketOptionChartRegionExtractor,
)


@pytest.mark.parametrize(
    (
        "extractor",
        "expected",
    ),
    [
        (
            FixedChartRegionExtractor(
                region=ChartRegion(
                    x=10,
                    y=20,
                    width=50,
                    height=40,
                )
            ),
            ChartRegion(
                x=10,
                y=20,
                width=50,
                height=40,
            ),
        ),
        (
            PocketOptionChartRegionExtractor(),
            ChartRegion(
                x=0,
                y=10,
                width=172,
                height=75,
            ),
        ),
    ],
    ids=[
        "fixed_region",
        "pocket_option_region",
    ],
)
def test_runtime_extractors_implement_chart_region_contract(
    extractor: ChartRegionExtractor,
    expected: ChartRegion,
) -> None:

    image = np.zeros(
        (
            100,
            200,
            3,
        ),
        dtype=np.uint8,
    )

    assert isinstance(
        extractor,
        ChartRegionExtractor,
    )

    result = extractor.extract(
        image,
    )

    assert isinstance(
        result,
        ChartRegion,
    )

    assert result == expected
