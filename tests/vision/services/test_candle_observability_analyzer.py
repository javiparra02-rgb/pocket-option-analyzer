from __future__ import annotations

import pytest

from pocket_option_analyzer.vision.models import (
    CandleCloseBoundary,
    CandleGeometry,
    CandleObservability,
    CandleType,
)
from pocket_option_analyzer.vision.services import CandleObservabilityAnalyzer


def test_analyzer_derives_body_boundary_facts_from_existing_geometry() -> None:
    result = CandleObservabilityAnalyzer.analyze(
        geometry=CandleGeometry(0, 0, 80, 99),
        roi_height=100,
    )

    assert result == CandleObservability(
        roi_height=100,
        body_top_y=0,
        body_bottom_y=80,
        body_touches_top=True,
        body_touches_bottom=False,
    )
    assert result.close_boundary_for(CandleType.BULLISH) is (
        CandleCloseBoundary.BODY_TOP
    )
    assert result.fully_observable_close_for(CandleType.BULLISH) is False
    assert result.close_boundary_for(CandleType.BEARISH) is (
        CandleCloseBoundary.BODY_BOTTOM
    )
    assert result.fully_observable_close_for(CandleType.BEARISH) is True


def test_analyzer_marks_bottom_body_edge_without_reanalyzing_pixels() -> None:
    result = CandleObservabilityAnalyzer.analyze(
        geometry=CandleGeometry(10, 20, 99, 99),
        roi_height=100,
    )

    assert result.body_touches_top is False
    assert result.body_touches_bottom is True
    assert result.fully_observable_close_for(CandleType.BULLISH) is True
    assert result.fully_observable_close_for(CandleType.BEARISH) is False


def test_unknown_candle_has_no_close_observability_claim() -> None:
    result = CandleObservabilityAnalyzer.analyze(
        geometry=CandleGeometry(10, 20, 30, 40),
        roi_height=100,
    )

    assert result.close_boundary_for(CandleType.UNKNOWN) is None
    assert result.fully_observable_close_for(CandleType.UNKNOWN) is None


@pytest.mark.parametrize(
    "observability",
    (
        CandleObservability(
            roi_height=100,
            body_top_y=20,
            body_bottom_y=30,
            body_touches_top=False,
            body_touches_bottom=False,
        ),
    ),
)
def test_observability_is_immutable(observability: CandleObservability) -> None:
    with pytest.raises(AttributeError):
        observability.roi_height = 200  # type: ignore[misc]


def test_observability_rejects_incoherent_boundary_flags() -> None:
    with pytest.raises(ValueError, match="body_touches_bottom"):
        CandleObservability(
            roi_height=100,
            body_top_y=20,
            body_bottom_y=99,
            body_touches_top=False,
            body_touches_bottom=False,
        )
