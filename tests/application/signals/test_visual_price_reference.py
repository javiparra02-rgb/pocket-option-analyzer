import pytest

from pocket_option_analyzer.application.signals.visual_strategy_signal_analysis_pipeline import (  # noqa: E501
    VisualStrategySignalAnalysisPipeline,
)
from pocket_option_analyzer.application.strategy import (
    VisualPriceReference,
    VisualPriceReferenceStatus,
)
from pocket_option_analyzer.vision.models import (
    CandleAnchorExclusionReason,
    CandleCandidate,
    CandleCandidateDecision,
    CandleCandidateTrace,
    CandleDetectionTrace,
    CandleGeometry,
    CandleObservability,
    CandleSeries,
    CandleType,
    CandleWidthDecisionReason,
    ClassifiedCandle,
    FinalCandleTrace,
    MarketAnalysis,
    TrendDirection,
)


def _candle(
    x: int,
    candle_type: CandleType,
    coordinates: tuple[int, int, int, int] | None,
    *,
    roi_height: int = 1_000,
) -> ClassifiedCandle:
    geometry = CandleGeometry(*coordinates) if coordinates is not None else None
    observability = (
        CandleObservability(
            roi_height=roi_height,
            body_top_y=geometry.body_top_y,
            body_bottom_y=geometry.body_bottom_y,
            body_touches_top=geometry.body_top_y == 0,
            body_touches_bottom=geometry.body_bottom_y == roi_height - 1,
        )
        if geometry is not None
        else None
    )

    return ClassifiedCandle(
        candidate=CandleCandidate(
            x=x,
            y=coordinates[0] if coordinates is not None else 0,
            width=8,
            height=(coordinates[3] - coordinates[0] + 1) if coordinates else 1,
            area=20,
            geometry=geometry,
            observability=observability,
        ),
        candle_type=candle_type,
    )


def _reference_result(
    candles: tuple[ClassifiedCandle, ...],
):
    return VisualStrategySignalAnalysisPipeline._price_reference_result(
        MarketAnalysis(
            series=CandleSeries(candles),
            trend=TrendDirection.SIDEWAYS,
        )
    )


def test_reference_reports_latest_candle_missing() -> None:
    result = _reference_result(())

    assert result.reference is None
    assert result.status is VisualPriceReferenceStatus.LATEST_CANDLE_MISSING
    assert result.anchor_count == 0


def test_reference_reports_latest_geometry_missing() -> None:
    result = _reference_result(
        (
            _candle(
                10,
                CandleType.BULLISH,
                (100, 120, 140, 160),
            ),
            _candle(
                20,
                CandleType.BEARISH,
                (180, 200, 220, 240),
            ),
            _candle(
                30,
                CandleType.BULLISH,
                None,
            ),
        )
    )

    assert result.reference is None
    assert result.status is VisualPriceReferenceStatus.LATEST_GEOMETRY_MISSING
    assert result.latest_candle_type == CandleType.BULLISH.value
    assert result.latest_candidate_x == 30


def test_reference_reports_latest_candle_not_directional() -> None:
    result = _reference_result(
        (
            _candle(
                10,
                CandleType.BULLISH,
                (100, 120, 140, 160),
            ),
            _candle(
                20,
                CandleType.BEARISH,
                (180, 200, 220, 240),
            ),
            _candle(
                30,
                CandleType.UNKNOWN,
                (150, 160, 170, 180),
            ),
        )
    )

    assert result.reference is None
    assert result.status is VisualPriceReferenceStatus.LATEST_CANDLE_NOT_DIRECTIONAL
    assert result.latest_candle_type == CandleType.UNKNOWN.value
    assert result.anchor_count == 2


def test_reference_reports_insufficient_anchors() -> None:
    result = _reference_result(
        (
            _candle(
                10,
                CandleType.BULLISH,
                (100, 120, 140, 160),
            ),
            _candle(
                20,
                CandleType.BULLISH,
                (110, 120, 130, 150),
            ),
        )
    )

    assert result.reference is None
    assert result.status is VisualPriceReferenceStatus.INSUFFICIENT_ANCHORS
    assert result.anchor_count == 1


def test_reference_reports_zero_anchor_range() -> None:
    result = _reference_result(
        (
            _candle(
                10,
                CandleType.BULLISH,
                (100, 100, 100, 100),
            ),
            _candle(
                20,
                CandleType.BEARISH,
                (100, 100, 100, 100),
            ),
            _candle(
                30,
                CandleType.BULLISH,
                (100, 100, 100, 100),
            ),
        )
    )

    assert result.reference is None
    assert result.status is VisualPriceReferenceStatus.ZERO_ANCHOR_RANGE
    assert result.anchor_count == 2
    assert result.anchor_top_roi_y == 100
    assert result.anchor_bottom_roi_y == 100


def test_reference_returns_ok_for_upper_breakout_without_clamping() -> None:
    result = _reference_result(
        (
            _candle(
                10,
                CandleType.BULLISH,
                (526, 550, 570, 600),
            ),
            _candle(
                20,
                CandleType.BEARISH,
                (650, 670, 710, 782),
            ),
            _candle(
                30,
                CandleType.BULLISH,
                (500, 514, 520, 530),
            ),
        )
    )

    assert result.status is VisualPriceReferenceStatus.OK
    assert result.reference is not None
    assert result.is_available
    assert result.anchor_count == 2
    assert result.close_roi_y == 514
    assert result.anchor_top_roi_y == 526
    assert result.anchor_bottom_roi_y == 782
    assert result.raw_normalized_close == pytest.approx(1.046875)
    assert result.raw_normalized_close > 1.0
    assert result.reference.value == pytest.approx(1.046875)
    assert result.reference.normalized_close == pytest.approx(1.046875)


def test_reference_returns_ok_for_lower_breakout_without_clamping() -> None:
    result = _reference_result(
        (
            _candle(10, CandleType.BULLISH, (100, 120, 140, 160)),
            _candle(20, CandleType.BEARISH, (180, 200, 220, 240)),
            _candle(30, CandleType.BEARISH, (230, 240, 250, 260)),
        )
    )

    assert result.status is VisualPriceReferenceStatus.OK
    assert result.reference is not None
    assert result.is_available
    assert result.raw_normalized_close == pytest.approx(-10.0 / 140.0)
    assert result.raw_normalized_close < 0.0
    assert result.reference.value == pytest.approx(-10.0 / 140.0)
    assert result.reference.normalized_close == pytest.approx(-10.0 / 140.0)


@pytest.mark.parametrize("value", (100.0, -100.0))
def test_reference_preserves_extreme_finite_affine_values(value: float) -> None:
    reference = VisualPriceReference(value)

    assert reference.value == value
    assert reference.normalized_close == value


@pytest.mark.parametrize("value", (float("nan"), float("inf"), float("-inf")))
def test_reference_rejects_non_finite_affine_values(value: float) -> None:
    with pytest.raises(ValueError, match="value debe ser finito"):
        VisualPriceReference(value)


def test_reference_returns_ok_for_valid_geometry() -> None:
    result = _reference_result(
        (
            _candle(
                10,
                CandleType.BULLISH,
                (100, 120, 140, 160),
            ),
            _candle(
                20,
                CandleType.BEARISH,
                (180, 200, 220, 240),
            ),
            _candle(
                30,
                CandleType.BULLISH,
                (145, 150, 170, 190),
            ),
        )
    )

    assert result.status is VisualPriceReferenceStatus.OK
    assert result.reference is not None
    assert result.is_available

    assert result.anchor_count == 2
    assert result.close_roi_y == 150
    assert result.anchor_top_roi_y == 100
    assert result.anchor_bottom_roi_y == 240

    assert result.raw_normalized_close is not None
    assert 0.0 <= result.raw_normalized_close <= 1.0

    assert result.reference.value == result.raw_normalized_close


def test_reference_fails_closed_when_latest_observability_is_missing() -> None:
    latest_geometry = CandleGeometry(145, 150, 170, 190)
    latest = ClassifiedCandle(
        candidate=CandleCandidate(
            x=30,
            y=145,
            width=8,
            height=46,
            area=20,
            geometry=latest_geometry,
        ),
        candle_type=CandleType.BULLISH,
    )

    result = _reference_result(
        (
            _candle(10, CandleType.BULLISH, (100, 120, 140, 160)),
            _candle(20, CandleType.BEARISH, (180, 200, 220, 240)),
            latest,
        )
    )

    assert result.status is (
        VisualPriceReferenceStatus.CURRENT_CLOSE_NOT_OBSERVABLE
    )
    assert result.reference is None
    assert result.close_roi_y == 150


@pytest.mark.parametrize(
    ("candle_type", "coordinates"),
    (
        (CandleType.BULLISH, (0, 0, 20, 40)),
        (CandleType.BEARISH, (200, 220, 299, 299)),
    ),
)
def test_reference_rejects_close_defining_body_edge_at_roi_boundary(
    candle_type: CandleType,
    coordinates: tuple[int, int, int, int],
) -> None:
    result = _reference_result(
        (
            _candle(10, CandleType.BULLISH, (100, 120, 140, 160), roi_height=300),
            _candle(20, CandleType.BEARISH, (180, 200, 220, 240), roi_height=300),
            _candle(30, candle_type, coordinates, roi_height=300),
        )
    )

    assert result.status is (
        VisualPriceReferenceStatus.CURRENT_CLOSE_NOT_OBSERVABLE
    )
    assert result.reference is None
    assert result.close_roi_y == (
        coordinates[1]
        if candle_type is CandleType.BULLISH
        else coordinates[2]
    )
    assert result.raw_normalized_close is not None


@pytest.mark.parametrize(
    ("candle_type", "coordinates", "expected_close"),
    (
        (CandleType.BULLISH, (100, 120, 140, 299), 120),
        (CandleType.BEARISH, (0, 120, 140, 160), 140),
        (CandleType.BULLISH, (100, 120, 299, 299), 120),
        (CandleType.BEARISH, (0, 0, 140, 160), 140),
    ),
)
def test_reference_accepts_opposite_edge_or_wick_contact_when_close_is_interior(
    candle_type: CandleType,
    coordinates: tuple[int, int, int, int],
    expected_close: int,
) -> None:
    result = _reference_result(
        (
            _candle(10, CandleType.BULLISH, (100, 120, 140, 160), roi_height=300),
            _candle(20, CandleType.BEARISH, (180, 200, 220, 240), roi_height=300),
            _candle(30, candle_type, coordinates, roi_height=300),
        )
    )

    assert result.status is VisualPriceReferenceStatus.OK
    assert result.reference is not None
    assert result.close_roi_y == expected_close


@pytest.mark.parametrize(
    ("x", "body_top_y"),
    ((698, 713), (698, 770), (673, 696), (673, 769)),
)
def test_reference_rejects_session_05_like_bearish_bottom_crop(
    x: int,
    body_top_y: int,
) -> None:
    result = _reference_result(
        (
            _candle(10, CandleType.BULLISH, (167, 200, 300, 400), roi_height=788),
            _candle(20, CandleType.BEARISH, (300, 400, 600, 787), roi_height=788),
            _candle(
                x,
                CandleType.BEARISH,
                (body_top_y - 8, body_top_y, 787, 787),
                roi_height=788,
            ),
        )
    )

    assert result.status is (
        VisualPriceReferenceStatus.CURRENT_CLOSE_NOT_OBSERVABLE
    )
    assert result.reference is None
    assert result.close_roi_y == 787
    assert result.raw_normalized_close == 0.0


def test_reference_is_stable_under_uniform_translation_and_scale() -> None:
    original_result = _reference_result(
        (
            _candle(
                10,
                CandleType.BULLISH,
                (100, 120, 140, 160),
            ),
            _candle(
                20,
                CandleType.BEARISH,
                (180, 200, 220, 240),
            ),
            _candle(
                30,
                CandleType.BULLISH,
                (145, 150, 170, 190),
            ),
        )
    )

    transformed_result = _reference_result(
        (
            _candle(
                10,
                CandleType.BULLISH,
                (250, 290, 330, 370),
            ),
            _candle(
                20,
                CandleType.BEARISH,
                (410, 450, 490, 530),
            ),
            _candle(
                30,
                CandleType.BULLISH,
                (340, 350, 390, 430),
            ),
        )
    )

    assert original_result.status is VisualPriceReferenceStatus.OK
    assert transformed_result.status is VisualPriceReferenceStatus.OK

    original = original_result.reference
    transformed = transformed_result.reference

    assert original is not None
    assert transformed is not None

    assert transformed.value == original.value
    assert transformed.anchor_shape == original.anchor_shape


def test_reference_roles_observe_exact_latest_anchors_and_non_eligible() -> None:
    candles = (
        _candle(10, CandleType.BULLISH, (100, 120, 140, 160)),
        _candle(20, CandleType.UNKNOWN, (120, 130, 150, 180)),
        _candle(30, CandleType.BEARISH, (180, 200, 220, 240)),
        _candle(40, CandleType.BULLISH, (145, 150, 170, 190)),
    )
    candidate_ids = tuple(f"candidate_{index:03d}" for index in range(len(candles)))
    trace = CandleDetectionTrace(
        candidates=tuple(
            CandleCandidateTrace(
                candidate_id=candidate_id,
                x=candle.candidate.x,
                y=candle.candidate.y,
                width=candle.candidate.width,
                height=candle.candidate.height,
                area=candle.candidate.area,
                color=candle.candidate.color,
                decisions=(
                    CandleCandidateDecision.SEGMENTED,
                    CandleCandidateDecision.DIMENSION_ACCEPTED,
                    CandleCandidateDecision.WIDTH_ACCEPTED,
                    CandleCandidateDecision.RETURNED,
                ),
                dominant_width=8.0,
                width_decision_reason=(CandleWidthDecisionReason.WITHIN_DOMINANT_RANGE),
            )
            for candidate_id, candle in zip(candidate_ids, candles, strict=True)
        ),
        merges=(),
        returned_candidate_ids=candidate_ids,
        dominant_width=8.0,
        maximum_returned_candidates=80,
        final_candles=tuple(
            FinalCandleTrace(
                candidate_id=candidate_id,
                source_candidate_ids=(candidate_id,),
                ordinal=index,
                x=candle.candidate.x,
                y=candle.candidate.y,
                width=candle.candidate.width,
                height=candle.candidate.height,
                area=candle.candidate.area,
                color=candle.candidate.color,
                candle_type=candle.candle_type,
                geometry=candle.candidate.geometry,
                is_latest=index == len(candles) - 1,
                anchor_exclusion_reason=(
                    CandleAnchorExclusionReason.LATEST
                    if index == len(candles) - 1
                    else CandleAnchorExclusionReason.NOT_EVALUATED
                ),
            )
            for index, (candidate_id, candle) in enumerate(
                zip(candidate_ids, candles, strict=True)
            )
        ),
    )
    market_analysis = MarketAnalysis(
        series=CandleSeries(candles),
        trend=TrendDirection.SIDEWAYS,
        candle_detection_trace=trace,
    )

    reference_analysis = VisualStrategySignalAnalysisPipeline._price_reference_analysis(
        market_analysis
    )
    enriched = VisualStrategySignalAnalysisPipeline._with_reference_roles(
        market_analysis=market_analysis,
        reference_analysis=reference_analysis,
    )

    assert reference_analysis.result == (
        VisualStrategySignalAnalysisPipeline._price_reference_result(market_analysis)
    )
    final_candles = enriched.candle_detection_trace
    assert final_candles is not None
    roles = final_candles.final_candles
    assert roles[0].is_anchor is True
    assert roles[0].anchor_index == 0
    assert roles[1].is_latest is False
    assert roles[1].is_anchor is False
    assert roles[1].anchor_exclusion_reason is (
        CandleAnchorExclusionReason.UNKNOWN_CANDLE_TYPE
    )
    assert roles[2].is_anchor is True
    assert roles[2].anchor_index == 1
    assert roles[3].is_latest is True
    assert roles[3].is_anchor is False
    assert roles[3].anchor_exclusion_reason is CandleAnchorExclusionReason.LATEST
