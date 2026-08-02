import cv2
import numpy as np

from pocket_option_analyzer.vision.services import (
    PocketOptionCandleMaskBuilder,
)


def test_pocket_option_candle_mask_builder_detects_white_and_red_candles() -> None:

    image = np.zeros(
        (120, 160, 3),
        dtype=np.uint8,
    )

    image[:] = (
        25,
        27,
        40,
    )

    cv2.rectangle(
        image,
        (
            20,
            30,
        ),
        (
            35,
            90,
        ),
        (
            255,
            255,
            255,
        ),
        thickness=-1,
    )

    cv2.rectangle(
        image,
        (
            70,
            25,
        ),
        (
            85,
            95,
        ),
        (
            0,
            0,
            255,
        ),
        thickness=-1,
    )

    builder = PocketOptionCandleMaskBuilder()

    mask = builder.build(
        image=image,
    )

    assert mask[50, 25] > 0
    assert mask[50, 75] > 0
    assert mask[10, 10] == 0


def test_pocket_option_candle_mask_builder_ignores_dark_grid() -> None:

    image = np.zeros(
        (120, 160, 3),
        dtype=np.uint8,
    )

    image[:] = (
        25,
        27,
        40,
    )

    cv2.line(
        image,
        (
            0,
            60,
        ),
        (
            160,
            60,
        ),
        (
            55,
            58,
            75,
        ),
        thickness=1,
    )

    builder = PocketOptionCandleMaskBuilder()

    mask = builder.build(
        image=image,
    )

    assert int(mask.sum()) == 0


def test_pocket_option_candle_mask_builder_preserves_thin_wick_and_doji() -> None:

    image = np.zeros(
        (
            120,
            120,
            3,
        ),
        dtype=np.uint8,
    )
    image[:] = (
        25,
        27,
        40,
    )

    red = (
        0,
        0,
        255,
    )

    cv2.line(
        image,
        (
            60,
            20,
        ),
        (
            60,
            90,
        ),
        red,
        thickness=1,
    )
    cv2.rectangle(
        image,
        (
            40,
            54,
        ),
        (
            80,
            56,
        ),
        red,
        thickness=-1,
    )

    mask = PocketOptionCandleMaskBuilder().build(
        image=image,
    )

    assert mask[20, 60] > 0
    assert mask[55, 40] > 0
    assert mask[90, 60] > 0


def test_pocket_option_candle_mask_builder_does_not_merge_neighbors() -> None:

    image = np.zeros(
        (
            120,
            120,
            3,
        ),
        dtype=np.uint8,
    )
    image[:] = (
        25,
        27,
        40,
    )

    cv2.rectangle(
        image,
        (
            20,
            30,
        ),
        (
            40,
            90,
        ),
        (
            255,
            255,
            255,
        ),
        thickness=-1,
    )
    cv2.rectangle(
        image,
        (
            46,
            30,
        ),
        (
            66,
            90,
        ),
        (
            0,
            0,
            255,
        ),
        thickness=-1,
    )

    mask = PocketOptionCandleMaskBuilder().build(
        image=image,
    )

    assert (
        np.count_nonzero(
            mask[
                :,
                43,
            ]
        )
        == 0
    )
