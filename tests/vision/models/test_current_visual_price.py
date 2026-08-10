import pytest

from pocket_option_analyzer.vision.models import CurrentVisualPrice


def test_current_visual_price_accepts_valid_roi_position() -> None:
    price = CurrentVisualPrice(
        roi_y=250.0,
        normalized_roi_y=0.5,
        roi_width=1200,
        roi_height=500,
        source="current_visual_price_roi_v1",
        confidence=0.9,
    )

    assert price.roi_y == 250.0
    assert price.normalized_roi_y == 0.5
    assert price.roi_width == 1200
    assert price.roi_height == 500
    assert price.source == "current_visual_price_roi_v1"
    assert price.confidence == 0.9


@pytest.mark.parametrize(
    ("roi_width", "roi_height"),
    (
        (0, 500),
        (-1, 500),
        (1200, 1),
        (1200, 0),
    ),
)
def test_current_visual_price_rejects_invalid_roi_dimensions(
    roi_width: int,
    roi_height: int,
) -> None:
    with pytest.raises(ValueError):
        CurrentVisualPrice(
            roi_y=0.0,
            normalized_roi_y=0.5,
            roi_width=roi_width,
            roi_height=roi_height,
            source="current_visual_price_roi_v1",
        )


@pytest.mark.parametrize(
    "roi_y",
    (
        -1.0,
        500.0,
    ),
)
def test_current_visual_price_rejects_roi_y_outside_image(
    roi_y: float,
) -> None:
    with pytest.raises(ValueError):
        CurrentVisualPrice(
            roi_y=roi_y,
            normalized_roi_y=0.5,
            roi_width=1200,
            roi_height=500,
            source="current_visual_price_roi_v1",
        )


@pytest.mark.parametrize(
    "normalized_roi_y",
    (
        -0.01,
        1.01,
    ),
)
def test_current_visual_price_rejects_invalid_normalized_position(
    normalized_roi_y: float,
) -> None:
    with pytest.raises(ValueError):
        CurrentVisualPrice(
            roi_y=250.0,
            normalized_roi_y=normalized_roi_y,
            roi_width=1200,
            roi_height=500,
            source="current_visual_price_roi_v1",
        )


def test_current_visual_price_rejects_empty_source() -> None:
    with pytest.raises(ValueError):
        CurrentVisualPrice(
            roi_y=250.0,
            normalized_roi_y=0.5,
            roi_width=1200,
            roi_height=500,
            source="",
        )


@pytest.mark.parametrize(
    "confidence",
    (
        -0.01,
        1.01,
    ),
)
def test_current_visual_price_rejects_invalid_confidence(
    confidence: float,
) -> None:
    with pytest.raises(ValueError):
        CurrentVisualPrice(
            roi_y=250.0,
            normalized_roi_y=0.5,
            roi_width=1200,
            roi_height=500,
            source="current_visual_price_roi_v1",
            confidence=confidence,
        )