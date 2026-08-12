from datetime import datetime

import numpy as np

from pocket_option_analyzer.infrastructure.capture.models import Frame
from pocket_option_analyzer.vision.models import ChartRegion


def test_frame_dimensions() -> None:
    image = np.zeros((720, 1280, 3), dtype=np.uint8)

    frame = Frame(
        frame_id=1,
        timestamp=datetime.now(),
        image=image,
    )

    assert frame.width == 1280
    assert frame.height == 720
    assert frame.channels == 3
    assert frame.price_observation_image is None
    assert frame.chart_region is None
    assert frame.price_observation_region is None


def test_frame_accepts_price_observation_image() -> None:
    image = np.zeros((720, 1280, 3), dtype=np.uint8)
    price_observation_image = np.ones((800, 1280, 3), dtype=np.uint8)

    frame = Frame(
        frame_id=1,
        timestamp=datetime.now(),
        image=image,
        price_observation_image=price_observation_image,
    )

    assert frame.image is image
    assert frame.price_observation_image is price_observation_image
    assert frame.width == 1280
    assert frame.height == 720
    assert frame.channels == 3


def test_frame_preserves_optional_capture_regions_by_identity() -> None:
    chart_region = ChartRegion(x=10, y=20, width=100, height=80)
    price_region = ChartRegion(x=30, y=40, width=100, height=80)

    frame = Frame(
        frame_id=1,
        timestamp=datetime.now(),
        image=np.zeros((80, 100, 3), dtype=np.uint8),
        chart_region=chart_region,
        price_observation_region=price_region,
    )

    assert frame.chart_region is chart_region
    assert frame.price_observation_region is price_region
