import numpy as np

from pocket_option_analyzer.infrastructure.capture import FrameFactory
from pocket_option_analyzer.vision.models import ChartRegion


def test_frame_factory_generates_incremental_ids() -> None:
    factory = FrameFactory()

    image = np.zeros((10, 10, 4), dtype=np.uint8)

    frame1 = factory.create(image)
    frame2 = factory.create(image)

    assert frame1.frame_id == 1
    assert frame2.frame_id == 2

    assert frame2.frame_id > frame1.frame_id
    assert frame1.price_observation_image is None
    assert frame1.chart_region is None
    assert frame1.price_observation_region is None


def test_frame_factory_propagates_both_images_by_identity() -> None:
    factory = FrameFactory()
    image = np.zeros((10, 10, 4), dtype=np.uint8)
    price_observation_image = np.ones((12, 10, 4), dtype=np.uint8)

    frame = factory.create(
        image=image,
        price_observation_image=price_observation_image,
    )

    assert frame.image is image
    assert frame.price_observation_image is price_observation_image


def test_frame_factory_propagates_capture_regions_by_identity() -> None:
    chart_region = ChartRegion(x=10, y=20, width=100, height=80)
    price_region = ChartRegion(x=30, y=40, width=100, height=80)

    frame = FrameFactory().create(
        image=np.zeros((80, 100, 4), dtype=np.uint8),
        chart_region=chart_region,
        price_observation_region=price_region,
    )

    assert frame.chart_region is chart_region
    assert frame.price_observation_region is price_region


def test_frame_factory_keeps_ids_monotonic_during_long_session() -> None:

    factory = FrameFactory()

    image = np.zeros(
        (1, 1, 4),
        dtype=np.uint8,
    )

    for expected_frame_id in range(
        1,
        10_001,
    ):
        frame = factory.create(
            image,
        )

        assert frame.frame_id == expected_frame_id


def test_frame_factory_creates_timezone_aware_utc_timestamp() -> None:

    factory = FrameFactory()

    image = np.zeros(
        (10, 10, 4),
        dtype=np.uint8,
    )

    frame = factory.create(
        image,
    )

    assert frame.timestamp.tzinfo is not None
    assert frame.timestamp.utcoffset() is not None
    assert frame.timestamp.utcoffset().total_seconds() == 0
