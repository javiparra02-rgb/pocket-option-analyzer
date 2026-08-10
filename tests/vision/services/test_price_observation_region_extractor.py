import numpy as np
import pytest

from pocket_option_analyzer.vision.models import ChartRegion
from pocket_option_analyzer.vision.services import (
    PocketOptionChartRegionExtractor,
    PocketOptionPriceObservationRegionExtractor,
    PriceObservationRegionExtractor,
)


def _image(
    *,
    height: int = 100,
    width: int = 200,
) -> np.ndarray:
    return np.zeros(
        (
            height,
            width,
            3,
        ),
        dtype=np.uint8,
    )


def test_runtime_extractor_implements_price_observation_region_contract() -> None:

    extractor: PriceObservationRegionExtractor = (
        PocketOptionPriceObservationRegionExtractor()
    )

    assert isinstance(
        extractor,
        PriceObservationRegionExtractor,
    )

    assert isinstance(
        extractor.extract(
            _image(),
        ),
        ChartRegion,
    )


def test_default_region_matches_current_chart_region_geometry() -> None:

    image = _image()
    chart_region = PocketOptionChartRegionExtractor().extract(
        image,
    )

    price_region = PocketOptionPriceObservationRegionExtractor().extract(
        image,
    )

    assert price_region == chart_region
    assert price_region is not chart_region


def test_bottom_extension_changes_only_price_region_vertical_boundary() -> None:

    image = _image()
    chart_extractor = PocketOptionChartRegionExtractor()
    chart_region_before = chart_extractor.extract(
        image,
    )

    price_region = PocketOptionPriceObservationRegionExtractor(
        bottom_extension_ratio=0.05,
    ).extract(
        image,
    )
    chart_region_after = chart_extractor.extract(
        image,
    )

    assert price_region.x == chart_region_before.x
    assert price_region.y == chart_region_before.y
    assert price_region.width == chart_region_before.width
    assert price_region.height == chart_region_before.height + 5
    assert price_region.bottom == chart_region_before.bottom + 5
    assert chart_region_after == chart_region_before
    assert chart_region_after is not chart_region_before
    assert price_region is not chart_region_before


def test_maximum_bottom_extension_stays_within_frame() -> None:

    image = _image()

    region = PocketOptionPriceObservationRegionExtractor(
        bottom_extension_ratio=0.15,
    ).extract(
        image,
    )

    assert region.bottom == image.shape[0]
    assert region.fits_within(
        image_width=image.shape[1],
        image_height=image.shape[0],
    )


@pytest.mark.parametrize(
    (
        "parameter",
        "value",
        "exception",
        "message",
    ),
    [
        (
            "top_ratio",
            True,
            TypeError,
            "top_ratio must be a real number",
        ),
        (
            "right_ratio",
            "0.14",
            TypeError,
            "right_ratio must be a real number",
        ),
        (
            "bottom_ratio",
            float("inf"),
            ValueError,
            "bottom_ratio must be finite",
        ),
        (
            "bottom_extension_ratio",
            -0.01,
            ValueError,
            r"bottom_extension_ratio must be in range \[0, 1\)",
        ),
    ],
)
def test_rejects_invalid_ratio(
    parameter: str,
    value: object,
    exception: type[Exception],
    message: str,
) -> None:

    with pytest.raises(
        exception,
        match=message,
    ):
        PocketOptionPriceObservationRegionExtractor(
            **{
                parameter: value,
            }
        )


def test_rejects_vertical_ratios_without_positive_base_region() -> None:

    with pytest.raises(
        ValueError,
        match="must sum to less than one",
    ):
        PocketOptionPriceObservationRegionExtractor(
            top_ratio=0.60,
            bottom_ratio=0.40,
        )


def test_rejects_extension_beyond_available_bottom_margin() -> None:

    with pytest.raises(
        ValueError,
        match="cannot exceed the bottom ratio",
    ):
        PocketOptionPriceObservationRegionExtractor(
            bottom_ratio=0.10,
            bottom_extension_ratio=0.11,
        )


def test_rejects_invalid_image() -> None:

    with pytest.raises(
        ValueError,
        match="requires a valid uint8 BGR or BGRA image",
    ):
        PocketOptionPriceObservationRegionExtractor().extract(
            np.zeros(
                (100,),
                dtype=np.uint8,
            )
        )
