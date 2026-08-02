from __future__ import annotations

import pytest

from pocket_option_analyzer.vision.models import (
    CandleGeometry,
)


def test_candle_geometry_calculates_body_and_wicks() -> None:

    geometry = CandleGeometry(
        high_y=10,
        body_top_y=25,
        body_bottom_y=55,
        low_y=70,
    )

    assert geometry.upper_wick_height == 15
    assert geometry.body_height == 31
    assert geometry.lower_wick_height == 15
    assert geometry.total_height == 61
    assert geometry.is_doji_like is False


def test_candle_geometry_rejects_invalid_vertical_order() -> None:

    with pytest.raises(
        ValueError,
        match="high_y <= body_top_y",
    ):
        CandleGeometry(
            high_y=30,
            body_top_y=20,
            body_bottom_y=50,
            low_y=70,
        )
