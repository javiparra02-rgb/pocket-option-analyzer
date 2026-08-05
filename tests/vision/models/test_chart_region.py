import pytest

from pocket_option_analyzer.vision.models import ChartRegion


def test_chart_region_exposes_derived_geometry() -> None:

    region = ChartRegion(
        x=10,
        y=20,
        width=30,
        height=40,
    )

    assert region.x == 10
    assert region.y == 20
    assert region.width == 30
    assert region.height == 40
    assert region.right == 40
    assert region.bottom == 60
    assert region.area == 1_200
    assert region.has_positive_area is True


def test_chart_region_accepts_exact_image_boundary() -> None:

    region = ChartRegion(
        x=20,
        y=10,
        width=80,
        height=90,
    )

    assert region.right == 100
    assert region.bottom == 100

    assert region.fits_within(
        image_width=100,
        image_height=100,
    )


@pytest.mark.parametrize(
    "region",
    [
        ChartRegion(
            x=-1,
            y=0,
            width=10,
            height=10,
        ),
        ChartRegion(
            x=0,
            y=-1,
            width=10,
            height=10,
        ),
        ChartRegion(
            x=0,
            y=0,
            width=0,
            height=10,
        ),
        ChartRegion(
            x=0,
            y=0,
            width=10,
            height=0,
        ),
        ChartRegion(
            x=91,
            y=0,
            width=10,
            height=10,
        ),
        ChartRegion(
            x=0,
            y=91,
            width=10,
            height=10,
        ),
    ],
    ids=[
        "negative_x",
        "negative_y",
        "zero_width",
        "zero_height",
        "outside_right",
        "outside_bottom",
    ],
)
def test_chart_region_rejects_invalid_image_bounds(
    region: ChartRegion,
) -> None:

    assert not region.fits_within(
        image_width=100,
        image_height=100,
    )
