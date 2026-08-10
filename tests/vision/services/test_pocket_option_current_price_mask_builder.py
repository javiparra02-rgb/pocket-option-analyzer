import cv2
import numpy as np
import pytest

from pocket_option_analyzer.vision.services import (
    PocketOptionCurrentPriceMaskBuilder,
)


def _bgr_from_hsv(hue: int, saturation: int, value: int) -> tuple[int, int, int]:
    hsv = np.array([[[hue, saturation, value]]], dtype=np.uint8)
    bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    return tuple(int(channel) for channel in bgr[0, 0])


def test_current_price_mask_detects_segment_inside_default_range() -> None:
    image = np.zeros((20, 30, 3), dtype=np.uint8)
    image[8, 4:26] = _bgr_from_hsv(109, 95, 126)

    mask = PocketOptionCurrentPriceMaskBuilder().build(image=image)

    assert np.all(mask[8, 4:26] == 255)
    assert mask[0, 0] == 0


def test_current_price_mask_ignores_pixel_outside_range() -> None:
    image = np.array([[ _bgr_from_hsv(80, 95, 126) ]], dtype=np.uint8)

    mask = PocketOptionCurrentPriceMaskBuilder().build(image=image)

    assert mask[0, 0] == 0


def test_current_price_mask_accepts_bgra() -> None:
    blue_gray = _bgr_from_hsv(109, 95, 126)
    image = np.array([[(*blue_gray, 37)]], dtype=np.uint8)

    mask = PocketOptionCurrentPriceMaskBuilder().build(image=image)

    assert mask[0, 0] == 255


def test_current_price_mask_rejects_invalid_image_like_existing_builder() -> None:
    image = np.zeros((10, 10), dtype=np.uint8)

    with pytest.raises(cv2.error):
        PocketOptionCurrentPriceMaskBuilder().build(image=image)


def test_current_price_mask_ignores_red_and_white() -> None:
    image = np.array([[[0, 0, 255], [255, 255, 255]]], dtype=np.uint8)

    mask = PocketOptionCurrentPriceMaskBuilder().build(image=image)

    assert np.count_nonzero(mask) == 0


def test_current_price_mask_returns_binary_uint8_with_image_shape() -> None:
    image = np.zeros((12, 17, 3), dtype=np.uint8)
    image[3, 5] = _bgr_from_hsv(109, 95, 126)

    mask = PocketOptionCurrentPriceMaskBuilder().build(image=image)

    assert mask.dtype == np.uint8
    assert mask.shape == image.shape[:2]
    assert set(np.unique(mask)).issubset({0, 255})


@pytest.mark.parametrize(
    ("kwargs", "error"),
    [
        ({"min_hue": -1}, ValueError),
        ({"max_hue": 181}, ValueError),
        ({"min_saturation": 161, "max_saturation": 160}, ValueError),
        ({"max_value": 256}, ValueError),
        ({"min_value": 90.0}, TypeError),
    ],
)
def test_current_price_mask_validates_configurable_ranges(
    kwargs: dict[str, object],
    error: type[Exception],
) -> None:
    with pytest.raises(error):
        PocketOptionCurrentPriceMaskBuilder(**kwargs)
