import numpy as np

from pocket_option_analyzer.vision.models import (
    CandleAnalysisResult,
    CandleAnchorExclusionReason,
    CandleCandidate,
    CandleCandidateDecision,
    CandleCandidateTrace,
    CandleColor,
    CandleDetectionTrace,
    CandleDimensionRejectionReason,
    CandleFilterDiagnostics,
    CandleGeometry,
    CandleSeries,
    CandleSeriesMembershipResult,
    CandleSeriesMembershipRunTrace,
    CandleSeriesMembershipStatus,
    CandleSeriesMembershipTrace,
    CandleType,
    CandleWidthDecisionReason,
    ChartRegion,
    ClassifiedCandle,
    CurrentVisualPrice,
    CurrentVisualPriceExtraction,
    CurrentVisualPriceStatus,
    TrendDirection,
)
from pocket_option_analyzer.vision.services import (
    MarketAnalysisPipeline,
    PocketOptionCurrentVisualPriceExtractor,
)


class FakeCandleAnalysisPipeline:
    last_detection_diagnostics = CandleFilterDiagnostics(
        input_count=23,
        dimension_valid_count=19,
        width_valid_count=12,
        merged_count=12,
        returned_count=12,
        dominant_width=34.0,
    )

    def __init__(self) -> None:
        self.received_image: np.ndarray | None = None

    def analyze(self, image):
        self.received_image = image
        return [
            ClassifiedCandle(
                candidate=CandleCandidate(
                    x=10,
                    y=20,
                    width=5,
                    height=30,
                    area=150,
                    color=CandleColor.GREEN,
                ),
                candle_type=CandleType.BULLISH,
            )
        ]


class FakeSeriesBuilder:
    def build(self, candles):
        return CandleSeries(
            candles=tuple(candles),
        )


class FakeMembershipResolver:
    def __init__(self) -> None:
        self.received_candles: tuple[ClassifiedCandle, ...] | None = None
        self.received_candidate_ids: tuple[str, ...] | None = None
        self.received_dominant_width: float | None = None

    def resolve(self, candles, candidate_ids, dominant_width):
        candles = tuple(candles)
        candidate_ids = tuple(candidate_ids)
        self.received_candles = candles
        self.received_candidate_ids = candidate_ids
        self.received_dominant_width = dominant_width
        if not candidate_ids:
            return CandleSeriesMembershipResult(
                candles=(),
                candidate_ids=(),
                trace=CandleSeriesMembershipTrace(
                    status=CandleSeriesMembershipStatus.INSUFFICIENT_SUPPORT,
                    evaluated_candidate_ids=(),
                    member_candidate_ids=(),
                    excluded_candidates=(),
                    evaluated_gaps=(),
                    estimated_pitch_px=None,
                    candidate_runs=(),
                    selected_run_support=0,
                    latest_candidate_id=None,
                    diagnostic="test_empty_input",
                ),
            )
        return CandleSeriesMembershipResult(
            candles=candles,
            candidate_ids=candidate_ids,
            trace=CandleSeriesMembershipTrace(
                status=CandleSeriesMembershipStatus.AVAILABLE,
                evaluated_candidate_ids=candidate_ids,
                member_candidate_ids=candidate_ids,
                excluded_candidates=(),
                evaluated_gaps=(),
                estimated_pitch_px=None,
                candidate_runs=(
                    CandleSeriesMembershipRunTrace(
                        run_id="run_000",
                        candidate_ids=candidate_ids,
                        selected=True,
                    ),
                ),
                selected_run_support=len(candidate_ids),
                latest_candidate_id=candidate_ids[-1],
                diagnostic="test_all_candidates_available",
            ),
        )


class FakeTrendDetector:
    def detect(self, series):
        return TrendDirection.BULLISH


class FakeCurrentVisualPriceExtractor:
    def __init__(
        self,
        result: CurrentVisualPriceExtraction,
    ) -> None:
        self.result = result
        self.received_image: np.ndarray | None = None

    def extract(
        self,
        image: np.ndarray,
    ) -> CurrentVisualPriceExtraction:
        self.received_image = image
        return self.result


def test_analyze_returns_market_analysis() -> None:

    pipeline = MarketAnalysisPipeline(
        candle_analysis_pipeline=FakeCandleAnalysisPipeline(),
        series_builder=FakeSeriesBuilder(),
        membership_resolver=FakeMembershipResolver(),
        trend_detector=FakeTrendDetector(),
    )

    result = pipeline.analyze(
        np.zeros(
            (100, 100, 3),
            dtype=np.uint8,
        )
    )

    assert len(result.series) == 1
    assert result.trend is TrendDirection.BULLISH


def test_market_analysis_preserves_detection_diagnostics() -> None:

    candle_pipeline = FakeCandleAnalysisPipeline()

    pipeline = MarketAnalysisPipeline(
        candle_analysis_pipeline=candle_pipeline,
        series_builder=FakeSeriesBuilder(),
        membership_resolver=FakeMembershipResolver(),
        trend_detector=FakeTrendDetector(),
    )

    result = pipeline.analyze(
        np.zeros(
            (100, 100, 3),
            dtype=np.uint8,
        )
    )

    assert result.detection_diagnostics is (candle_pipeline.last_detection_diagnostics)


def test_market_analysis_has_no_current_visual_price_without_extractor() -> None:
    pipeline = MarketAnalysisPipeline(
        candle_analysis_pipeline=FakeCandleAnalysisPipeline(),
        series_builder=FakeSeriesBuilder(),
        membership_resolver=FakeMembershipResolver(),
        trend_detector=FakeTrendDetector(),
    )

    result = pipeline.analyze(
        np.zeros(
            (100, 100, 3),
            dtype=np.uint8,
        )
    )

    assert result.current_visual_price is None


def test_market_analysis_preserves_current_visual_price_extraction() -> None:
    image = np.zeros(
        (100, 100, 3),
        dtype=np.uint8,
    )

    price = CurrentVisualPrice(
        roi_y=40.0,
        normalized_roi_y=1.0 - 40.0 / 99.0,
        roi_width=100,
        roi_height=100,
        source="pocket_option_right_band_v1",
        confidence=0.9,
    )

    extraction = CurrentVisualPriceExtraction(
        price=price,
        status=CurrentVisualPriceStatus.OK,
        candidate_count=1,
        selected_x=95.0,
        selected_y=40.0,
        confidence=0.9,
    )

    extractor = FakeCurrentVisualPriceExtractor(
        result=extraction,
    )

    pipeline = MarketAnalysisPipeline(
        candle_analysis_pipeline=FakeCandleAnalysisPipeline(),
        series_builder=FakeSeriesBuilder(),
        membership_resolver=FakeMembershipResolver(),
        trend_detector=FakeTrendDetector(),
        current_visual_price_extractor=extractor,
    )

    result = pipeline.analyze(image)

    assert result.current_visual_price is extraction
    assert extractor.received_image is image


def test_analyze_routes_each_image_to_its_exclusive_consumer() -> None:
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    price_observation_image = np.zeros((20, 100, 3), dtype=np.uint8)
    extraction = CurrentVisualPriceExtraction(
        price=None,
        status=CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE,
        candidate_count=0,
    )
    candle_pipeline = FakeCandleAnalysisPipeline()
    extractor = FakeCurrentVisualPriceExtractor(result=extraction)
    pipeline = MarketAnalysisPipeline(
        candle_analysis_pipeline=candle_pipeline,
        series_builder=FakeSeriesBuilder(),
        membership_resolver=FakeMembershipResolver(),
        trend_detector=FakeTrendDetector(),
        current_visual_price_extractor=extractor,
    )

    pipeline.analyze(
        image=image,
        price_observation_image=price_observation_image,
    )

    assert candle_pipeline.received_image is image
    assert extractor.received_image is price_observation_image


def test_analyze_uses_main_image_for_visual_price_when_second_image_is_none() -> None:
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    extraction = CurrentVisualPriceExtraction(
        price=None,
        status=CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE,
        candidate_count=0,
    )
    candle_pipeline = FakeCandleAnalysisPipeline()
    extractor = FakeCurrentVisualPriceExtractor(result=extraction)
    pipeline = MarketAnalysisPipeline(
        candle_analysis_pipeline=candle_pipeline,
        series_builder=FakeSeriesBuilder(),
        membership_resolver=FakeMembershipResolver(),
        trend_detector=FakeTrendDetector(),
        current_visual_price_extractor=extractor,
    )

    pipeline.analyze(image=image, price_observation_image=None)

    assert candle_pipeline.received_image is image
    assert extractor.received_image is image


def test_market_analysis_preserves_capture_geometry_by_identity() -> None:
    chart_region = ChartRegion(x=10, y=20, width=100, height=80)
    price_region = ChartRegion(x=30, y=40, width=100, height=80)
    pipeline = MarketAnalysisPipeline(
        candle_analysis_pipeline=FakeCandleAnalysisPipeline(),
        series_builder=FakeSeriesBuilder(),
        membership_resolver=FakeMembershipResolver(),
        trend_detector=FakeTrendDetector(),
    )

    result = pipeline.analyze(
        image=np.zeros((80, 100, 3), dtype=np.uint8),
        chart_region=chart_region,
        price_observation_region=price_region,
    )

    assert result.chart_region is chart_region
    assert result.price_observation_region is price_region


def test_market_analysis_preserves_current_price_trace_from_same_frame() -> None:
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    image[50, 80:100] = (126, 95, 79)
    pipeline = MarketAnalysisPipeline(
        candle_analysis_pipeline=FakeCandleAnalysisPipeline(),
        series_builder=FakeSeriesBuilder(),
        membership_resolver=FakeMembershipResolver(),
        trend_detector=FakeTrendDetector(),
        current_visual_price_extractor=PocketOptionCurrentVisualPriceExtractor(),
    )

    result = pipeline.analyze(image=image)

    assert result.current_visual_price is not None
    assert result.current_visual_price.status is CurrentVisualPriceStatus.OK
    trace = result.current_visual_price_detection_trace
    assert trace is not None
    assert trace.status is result.current_visual_price.status
    assert trace.candidates[0].y == result.current_visual_price.selected_y
    assert trace.candidates[0].selected is True


def test_left_final_candle_can_be_latest_after_right_candidate_rejection() -> None:
    geometry = CandleGeometry(
        high_y=20,
        body_top_y=25,
        body_bottom_y=40,
        low_y=45,
    )
    left = ClassifiedCandle(
        candidate=CandleCandidate(
            x=10,
            y=20,
            width=10,
            height=26,
            area=260,
            color=CandleColor.GREEN,
            geometry=geometry,
        ),
        candle_type=CandleType.BULLISH,
    )
    trace = CandleDetectionTrace(
        candidates=(
            CandleCandidateTrace(
                candidate_id="candidate_000",
                x=10,
                y=20,
                width=10,
                height=26,
                area=260,
                color=CandleColor.GREEN,
                decisions=(
                    CandleCandidateDecision.SEGMENTED,
                    CandleCandidateDecision.DIMENSION_ACCEPTED,
                    CandleCandidateDecision.WIDTH_ACCEPTED,
                    CandleCandidateDecision.RETURNED,
                ),
                dominant_width=10.0,
                width_decision_reason=(CandleWidthDecisionReason.WITHIN_DOMINANT_RANGE),
            ),
            CandleCandidateTrace(
                candidate_id="candidate_001",
                x=90,
                y=20,
                width=2,
                height=5,
                area=10,
                color=CandleColor.UNKNOWN,
                decisions=(
                    CandleCandidateDecision.SEGMENTED,
                    CandleCandidateDecision.REJECTED_DIMENSION,
                ),
                dimension_rejection_reasons=(
                    CandleDimensionRejectionReason.AREA_BELOW_MINIMUM,
                    CandleDimensionRejectionReason.WIDTH_BELOW_MINIMUM,
                ),
            ),
        ),
        merges=(),
        returned_candidate_ids=("candidate_000",),
        dominant_width=10.0,
        maximum_returned_candidates=80,
    )

    class TraceableCandleAnalysisPipeline(FakeCandleAnalysisPipeline):
        def analyze_with_trace(self, image):
            self.received_image = image
            return CandleAnalysisResult(
                candles=(left,),
                candidate_ids=("candidate_000",),
                trace=trace,
            )

    pipeline = MarketAnalysisPipeline(
        candle_analysis_pipeline=TraceableCandleAnalysisPipeline(),
        series_builder=FakeSeriesBuilder(),
        membership_resolver=FakeMembershipResolver(),
        trend_detector=FakeTrendDetector(),
    )

    result = pipeline.analyze(np.zeros((100, 100, 3), dtype=np.uint8))

    assert result.series.latest is left
    detection_trace = result.candle_detection_trace
    assert detection_trace is not None
    assert detection_trace.final_candles[0].is_latest is True
    assert detection_trace.final_candles[0].ordinal == 0
    assert detection_trace.final_candles[0].geometry is geometry
    assert detection_trace.final_candles[0].high_y == 20
    assert detection_trace.final_candles[0].body_top_y == 25
    assert detection_trace.final_candles[0].body_bottom_y == 40
    assert detection_trace.final_candles[0].low_y == 45
    assert detection_trace.final_candles[0].anchor_exclusion_reason is (
        CandleAnchorExclusionReason.LATEST
    )
    right_trace = detection_trace.candidates[1]
    assert right_trace.x > detection_trace.final_candles[0].x
    assert right_trace.decisions[-1] is CandleCandidateDecision.REJECTED_DIMENSION
