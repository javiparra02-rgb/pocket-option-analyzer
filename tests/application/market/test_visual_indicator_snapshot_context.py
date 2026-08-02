from __future__ import annotations

import pytest

from pocket_option_analyzer.application.market import (
    VisualIndicatorSnapshotContext,
)


def test_snapshot_context_detects_complete_geometry() -> None:

    context = VisualIndicatorSnapshotContext(
        visible_candle_count=18,
        ohlc_candle_count=17,
        geometry_valid_count=17,
        geometry_total_count=17,
    )

    assert context.has_complete_geometry is True


def test_snapshot_context_rejects_geometry_count_above_total() -> None:

    with pytest.raises(
        ValueError,
        match=("geometry_valid_count no puede superar geometry_total_count"),
    ):
        VisualIndicatorSnapshotContext(
            visible_candle_count=18,
            ohlc_candle_count=17,
            geometry_valid_count=18,
            geometry_total_count=17,
        )
