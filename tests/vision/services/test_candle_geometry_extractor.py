from __future__ import annotations

import cv2
import numpy as np

from pocket_option_analyzer.vision.models import (
    CandleCandidate,
    CandleGeometry,
)
from pocket_option_analyzer.vision.services import (
    CandleGeometryExtractor,
)


def test_candle_geometry_extractor_separates_body_and_wicks() -> None:

    mask = np.zeros(
        (
            100,
            100,
        ),
        dtype=np.uint8,
    )

    cv2.line(
        mask,
        (
            30,
            10,
        ),
        (
            30,
            70,
        ),
        255,
        thickness=1,
    )
    cv2.rectangle(
        mask,
        (
            20,
            25,
        ),
        (
            40,
            55,
        ),
        255,
        thickness=-1,
    )

    candidate = CandleCandidate(
        x=20,
        y=10,
        width=21,
        height=61,
        area=1281,
    )

    geometry = CandleGeometryExtractor().extract(
        mask=mask,
        candidate=candidate,
    )

    assert geometry == CandleGeometry(
        high_y=10,
        body_top_y=25,
        body_bottom_y=55,
        low_y=70,
    )


def test_candle_geometry_extractor_detects_one_pixel_doji() -> None:

    mask = np.zeros(
        (
            100,
            100,
        ),
        dtype=np.uint8,
    )

    cv2.line(
        mask,
        (
            30,
            15,
        ),
        (
            30,
            75,
        ),
        255,
        thickness=1,
    )
    cv2.rectangle(
        mask,
        (
            20,
            45,
        ),
        (
            40,
            45,
        ),
        255,
        thickness=-1,
    )

    candidate = CandleCandidate(
        x=20,
        y=15,
        width=21,
        height=61,
        area=1281,
    )

    geometry = CandleGeometryExtractor().extract(
        mask=mask,
        candidate=candidate,
    )

    assert geometry == CandleGeometry(
        high_y=15,
        body_top_y=45,
        body_bottom_y=45,
        low_y=75,
    )
    assert geometry.is_doji_like is True


def test_candle_geometry_extractor_rejects_isolated_vertical_line() -> None:

    mask = np.zeros(
        (
            100,
            100,
        ),
        dtype=np.uint8,
    )

    cv2.line(
        mask,
        (
            30,
            10,
        ),
        (
            30,
            70,
        ),
        255,
        thickness=1,
    )

    candidate = CandleCandidate(
        x=30,
        y=10,
        width=1,
        height=61,
        area=61,
    )

    geometry = CandleGeometryExtractor().extract(
        mask=mask,
        candidate=candidate,
    )

    assert geometry is None