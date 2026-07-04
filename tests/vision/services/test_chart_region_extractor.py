from pocket_option_analyzer.vision.services.chart_region_extractor import (
    ChartRegionExtractor,
)
from pocket_option_analyzer.infrastructure.windows.models import Win32WindowInfo


def test_extract_chart_region():
    extractor = ChartRegionExtractor()

    window = Win32WindowInfo(
        hwnd=1,
        title="Pocket Option",
        left=0,
        top=0,
        width=1000,
        height=600,
        client_left=0,
        client_top=0,
        client_width=1000,
        client_height=600,
        visible=True,
        minimized=False,
    )

    region = extractor.extract(window)

    assert region.left == 10
    assert region.top == 80
    assert region.width == 980
    assert region.height == 480