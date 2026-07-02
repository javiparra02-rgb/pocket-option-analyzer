from pocket_option_analyzer.vision.models import ChartRegion


def test_chart_region_properties() -> None:
    region = ChartRegion(
        x=10,
        y=20,
        width=30,
        height=40,
    )

    assert region.x == 10
    assert region.height == 40