from pocket_option_analyzer.application.signals.visual_strategy_signal_analysis_pipeline import (  # noqa: E501
    VisualStrategySignalAnalysisPipeline,
)
from pocket_option_analyzer.application.strategy import (
    VisualPriceReferenceStatus,
)
from pocket_option_analyzer.vision.models import (
    CandleCandidate,
    CandleGeometry,
    CandleSeries,
    CandleType,
    ClassifiedCandle,
    MarketAnalysis,
    TrendDirection,
)


def _candle(
    x: int,
    candle_type: CandleType,
    coordinates: tuple[int, int, int, int] | None,
) -> ClassifiedCandle:
    geometry = CandleGeometry(*coordinates) if coordinates is not None else None

    return ClassifiedCandle(
        candidate=CandleCandidate(
            x=x,
            y=coordinates[0] if coordinates is not None else 0,
            width=8,
            height=(coordinates[3] - coordinates[0] + 1) if coordinates else 1,
            area=20,
            geometry=geometry,
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


def test_reference_reports_close_outside_anchor_range() -> None:
    result = _reference_result(
        (
            _candle(
                10,
                CandleType.BULLISH,
                (490, 510, 530, 550),
            ),
            _candle(
                20,
                CandleType.BEARISH,
                (650, 670, 700, 750),
            ),
            _candle(
                30,
                CandleType.BULLISH,
                (5, 11, 20, 25),
            ),
        )
    )

    assert result.reference is None
    assert result.status is VisualPriceReferenceStatus.CLOSE_OUTSIDE_ANCHOR_RANGE

    assert result.anchor_count == 2
    assert result.close_roi_y == 11
    assert result.anchor_top_roi_y == 490
    assert result.anchor_bottom_roi_y == 750

    assert result.raw_normalized_close is not None
    assert result.raw_normalized_close > 1.0


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
