from __future__ import annotations

import numpy as np

from pocket_option_analyzer.application.market import VisualIndicatorSnapshotBuilder
from pocket_option_analyzer.application.signals import (
    VisualStrategySignalAnalysisPipeline,
)
from pocket_option_analyzer.application.strategy import VisualPriceReferenceStatus
from pocket_option_analyzer.domain.strategy import StrategyProfile
from pocket_option_analyzer.vision.models import (
    CandleAnalysisResult,
    CandleCandidate,
    CandleCandidateDecision,
    CandleCandidateTrace,
    CandleColor,
    CandleDetectionTrace,
    CandleFilterDiagnostics,
    CandleGeometry,
    CandleOverlayEvidenceStatus,
    CandleSeries,
    CandleSeriesMembershipExclusionReason,
    CandleSeriesMembershipStatus,
    CandleType,
    CandleWidthDecisionReason,
    ClassifiedCandle,
    TrendDirection,
)
from pocket_option_analyzer.vision.services import (
    CandleSeriesMembershipResolver,
    MarketAnalysisPipeline,
    PocketOptionExpiryOverlayEvidenceResolver,
    TrendDetector,
)


def _candle(
    *,
    x: int,
    open_y: int,
    close_y: int,
    width: int = 8,
) -> ClassifiedCandle:
    candle_type = (
        CandleType.BULLISH if close_y < open_y else CandleType.BEARISH
    )
    body_top_y = min(open_y, close_y)
    body_bottom_y = max(open_y, close_y)
    geometry = CandleGeometry(
        high_y=body_top_y - 2,
        body_top_y=body_top_y,
        body_bottom_y=body_bottom_y,
        low_y=body_bottom_y + 2,
    )
    return ClassifiedCandle(
        candidate=CandleCandidate(
            x=x,
            y=geometry.high_y,
            width=width,
            height=geometry.total_height,
            area=width * geometry.total_height,
            color=(
                CandleColor.WHITE
                if candle_type is CandleType.BULLISH
                else CandleColor.RED
            ),
            geometry=geometry,
        ),
        candle_type=candle_type,
    )


def _series(
    count: int,
    *,
    start_x: int = 0,
    start_y: int = 100,
    prefix: str = "real",
) -> tuple[tuple[ClassifiedCandle, ...], tuple[str, ...]]:
    prices = [start_y]
    for index in range(count):
        prices.append(prices[-1] + (-8 if index % 2 == 0 else 8))
    return (
        tuple(
            _candle(
                x=start_x + index * 12,
                open_y=prices[index],
                close_y=prices[index + 1],
            )
            for index in range(count)
        ),
        tuple(f"{prefix}_{index}" for index in range(count)),
    )


def _available_input() -> tuple[tuple[ClassifiedCandle, ...], tuple[str, ...]]:
    real_candles, real_ids = _series(6)
    flag = _candle(x=72, open_y=20, close_y=10)
    price_text = _candle(x=180, open_y=104, close_y=100)
    return real_candles + (flag, price_text), real_ids + ("flag", "price_text")


def _expiry_overlay_input() -> tuple[
    tuple[ClassifiedCandle, ...],
    tuple[str, ...],
    np.ndarray,
]:
    real_candles, real_ids = _series(6)
    overlay_geometry = CandleGeometry(
        high_y=10,
        body_top_y=10,
        body_bottom_y=21,
        low_y=21,
    )
    overlay = ClassifiedCandle(
        candidate=CandleCandidate(
            x=66,
            y=10,
            width=20,
            height=12,
            area=240,
            color=CandleColor.WHITE,
            geometry=overlay_geometry,
        ),
        candle_type=CandleType.BULLISH,
    )
    image = np.zeros((240, 120, 3), dtype=np.uint8)
    image[10:22, 66:86] = 255
    image[22:, 66:68] = 255
    return real_candles + (overlay,), real_ids + ("candidate_083",), image


def _trace(
    candles: tuple[ClassifiedCandle, ...],
    candidate_ids: tuple[str, ...],
    dominant_width: float = 8.0,
) -> CandleDetectionTrace:
    return CandleDetectionTrace(
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
                dominant_width=dominant_width,
                width_decision_reason=(
                    CandleWidthDecisionReason.WITHIN_DOMINANT_RANGE
                ),
            )
            for candle, candidate_id in zip(
                candles,
                candidate_ids,
                strict=True,
            )
        ),
        merges=(),
        returned_candidate_ids=candidate_ids,
        dominant_width=dominant_width,
        maximum_returned_candidates=80,
    )


class _TraceableAnalysisPipeline:
    def __init__(
        self,
        candles: tuple[ClassifiedCandle, ...],
        candidate_ids: tuple[str, ...],
    ) -> None:
        self.result = CandleAnalysisResult(
            candles=candles,
            candidate_ids=candidate_ids,
            trace=_trace(candles, candidate_ids),
        )
        self.last_detection_diagnostics = CandleFilterDiagnostics(
            input_count=len(candles),
            dimension_valid_count=len(candles),
            width_valid_count=len(candles),
            merged_count=len(candles),
            returned_count=len(candles),
            dominant_width=8.0,
        )

    def analyze_with_trace(self, image: np.ndarray) -> CandleAnalysisResult:
        return self.result

    def analyze(self, image: np.ndarray) -> list[ClassifiedCandle]:
        return list(self.result.candles)


class _RecordingSeriesBuilder:
    def __init__(self) -> None:
        self.received: tuple[ClassifiedCandle, ...] | None = None

    def build(self, candles) -> CandleSeries:
        self.received = tuple(candles)
        return CandleSeries(candles=self.received)


class _CapturingMembershipResolver:
    def __init__(self) -> None:
        self.delegate = CandleSeriesMembershipResolver()
        self.received_candles: tuple[ClassifiedCandle, ...] | None = None
        self.received_candidate_ids: tuple[str, ...] | None = None
        self.received_dominant_width: float | None = None
        self.received_overlay_evidence = None

    def resolve(
        self,
        candles,
        candidate_ids,
        dominant_width,
        overlay_evidence,
    ):
        self.received_candles = tuple(candles)
        self.received_candidate_ids = tuple(candidate_ids)
        self.received_dominant_width = dominant_width
        self.received_overlay_evidence = overlay_evidence
        return self.delegate.resolve(
            candles=self.received_candles,
            candidate_ids=self.received_candidate_ids,
            dominant_width=dominant_width,
            overlay_evidence=overlay_evidence,
        )


def _pipeline(
    candles: tuple[ClassifiedCandle, ...],
    candidate_ids: tuple[str, ...],
    *,
    builder: _RecordingSeriesBuilder | None = None,
    resolver: _CapturingMembershipResolver | None = None,
) -> tuple[MarketAnalysisPipeline, _RecordingSeriesBuilder]:
    resolved_builder = builder or _RecordingSeriesBuilder()
    return (
        MarketAnalysisPipeline(
            candle_analysis_pipeline=_TraceableAnalysisPipeline(
                candles,
                candidate_ids,
            ),
            series_builder=resolved_builder,
            membership_resolver=(resolver or _CapturingMembershipResolver()),
            overlay_evidence_resolver=(
                PocketOptionExpiryOverlayEvidenceResolver()
            ),
            trend_detector=TrendDetector(),
        ),
        resolved_builder,
    )


def test_available_members_only_reach_series_builder() -> None:
    candles, candidate_ids = _available_input()
    pipeline, builder = _pipeline(candles, candidate_ids)

    analysis = pipeline.analyze(np.zeros((10, 10, 3), dtype=np.uint8))

    assert builder.received == candles[:6]
    assert analysis.series.candles == candles[:6]


def test_flag_and_price_text_do_not_reach_productive_series() -> None:
    candles, candidate_ids = _available_input()
    pipeline, _ = _pipeline(candles, candidate_ids)

    analysis = pipeline.analyze(np.zeros((10, 10, 3), dtype=np.uint8))

    assert candles[6] not in analysis.series.candles
    assert candles[7] not in analysis.series.candles


def test_true_current_candle_is_productive_latest() -> None:
    candles, candidate_ids = _available_input()
    pipeline, _ = _pipeline(candles, candidate_ids)

    analysis = pipeline.analyze(np.zeros((10, 10, 3), dtype=np.uint8))

    assert analysis.series.latest is candles[5]
    assert analysis.candle_detection_trace is not None
    assert analysis.candle_detection_trace.series_membership is not None
    assert (
        analysis.candle_detection_trace.series_membership.latest_candidate_id
        == candidate_ids[5]
    )


def test_current_and_contaminants_are_absent_from_closed_anchors() -> None:
    candles, candidate_ids = _available_input()
    pipeline, _ = _pipeline(candles, candidate_ids)

    analysis = pipeline.analyze(np.zeros((10, 10, 3), dtype=np.uint8))
    closed = analysis.series.without_latest().candles

    assert closed == candles[:5]
    assert candles[5] not in closed
    assert candles[6] not in closed
    assert candles[7] not in closed


def test_reference_roles_map_members_onto_pre_membership_trace() -> None:
    candles, candidate_ids = _available_input()
    pipeline, _ = _pipeline(candles, candidate_ids)
    analysis = pipeline.analyze(np.zeros((10, 10, 3), dtype=np.uint8))
    reference_analysis = (
        VisualStrategySignalAnalysisPipeline._price_reference_analysis(analysis)
    )

    enriched = VisualStrategySignalAnalysisPipeline._with_reference_roles(
        market_analysis=analysis,
        reference_analysis=reference_analysis,
    )
    trace = enriched.candle_detection_trace
    assert trace is not None
    roles = {item.candidate_id: item for item in trace.final_candles}

    assert roles[candidate_ids[5]].is_latest is True
    assert roles[candidate_ids[5]].is_anchor is False
    assert roles["flag"].is_anchor is False
    assert roles["price_text"].is_anchor is False
    assert tuple(
        item.candidate_id
        for item in trace.final_candles
        if item.is_anchor
    ) == candidate_ids[:5]


def test_membership_exclusions_keep_structured_reasons() -> None:
    candles, candidate_ids = _available_input()
    pipeline, _ = _pipeline(candles, candidate_ids)

    analysis = pipeline.analyze(np.zeros((10, 10, 3), dtype=np.uint8))
    trace = analysis.candle_detection_trace
    assert trace is not None and trace.series_membership is not None
    exclusions = {
        exclusion.candidate_id: exclusion.reason
        for exclusion in trace.series_membership.excluded_candidates
    }

    assert exclusions["flag"] is (
        CandleSeriesMembershipExclusionReason.VERTICAL_DISCONTINUITY
    )
    assert exclusions["price_text"] is (
        CandleSeriesMembershipExclusionReason.HORIZONTAL_OUTLIER
    )


def test_expiry_overlay_remains_traceable_but_not_productive_or_anchor() -> None:
    candles, candidate_ids, image = _expiry_overlay_input()
    pipeline, _ = _pipeline(candles, candidate_ids)

    analysis = pipeline.analyze(image)
    trace = analysis.candle_detection_trace
    assert trace is not None
    assert trace.overlay_evidence is not None
    evidence = trace.overlay_evidence.by_candidate_id()["candidate_083"]
    assert evidence.status is CandleOverlayEvidenceStatus.EXPIRY_OVERLAY
    assert "candidate_083" in trace.returned_candidate_ids
    assert "candidate_083" in tuple(
        item.candidate_id for item in trace.final_candles
    )
    assert trace.series_membership is not None
    real_latest_id = candidate_ids[-2]
    assert trace.series_membership.latest_candidate_id == real_latest_id
    exclusions = {
        item.candidate_id: item.reason
        for item in trace.series_membership.excluded_candidates
    }
    assert exclusions["candidate_083"] is (
        CandleSeriesMembershipExclusionReason.EXPIRY_OVERLAY
    )

    reference_analysis = (
        VisualStrategySignalAnalysisPipeline._price_reference_analysis(analysis)
    )
    enriched = VisualStrategySignalAnalysisPipeline._with_reference_roles(
        market_analysis=analysis,
        reference_analysis=reference_analysis,
    )
    assert enriched.candle_detection_trace is not None
    roles = {
        item.candidate_id: item
        for item in enriched.candle_detection_trace.final_candles
    }
    assert roles["candidate_083"].is_latest is False
    assert roles["candidate_083"].is_anchor is False
    assert roles[real_latest_id].is_latest is True
    assert roles[real_latest_id].is_anchor is False


def test_frame_172_price_text_remains_horizontal_outlier() -> None:
    candles, candidate_ids = _series(6)
    price_text = _candle(x=1047, open_y=104, close_y=100, width=20)
    all_ids = candidate_ids + ("candidate_002",)
    pipeline, _ = _pipeline(candles + (price_text,), all_ids)

    analysis = pipeline.analyze(np.zeros((800, 1100, 3), dtype=np.uint8))
    membership = analysis.candle_detection_trace.series_membership
    assert membership is not None
    exclusion = next(
        item
        for item in membership.excluded_candidates
        if item.candidate_id == "candidate_002"
    )

    assert exclusion.reason is (
        CandleSeriesMembershipExclusionReason.HORIZONTAL_OUTLIER
    )


def test_pre_membership_final_candles_and_lifecycle_remain_intact() -> None:
    candles, candidate_ids = _available_input()
    source_pipeline = _TraceableAnalysisPipeline(candles, candidate_ids)
    pipeline = MarketAnalysisPipeline(
        candle_analysis_pipeline=source_pipeline,
        series_builder=_RecordingSeriesBuilder(),
        membership_resolver=_CapturingMembershipResolver(),
        overlay_evidence_resolver=PocketOptionExpiryOverlayEvidenceResolver(),
        trend_detector=TrendDetector(),
    )

    analysis = pipeline.analyze(np.zeros((10, 10, 3), dtype=np.uint8))
    trace = analysis.candle_detection_trace
    assert trace is not None

    assert trace.candidates is source_pipeline.result.trace.candidates
    assert tuple(item.candidate_id for item in trace.final_candles) == candidate_ids
    assert len(trace.final_candles) == len(candles)
    latest_trace = next(item for item in trace.final_candles if item.is_latest)
    assert latest_trace.candidate_id == candidate_ids[5]


def test_contaminants_remain_in_trace_without_latest_role() -> None:
    candles, candidate_ids = _available_input()
    pipeline, _ = _pipeline(candles, candidate_ids)

    analysis = pipeline.analyze(np.zeros((10, 10, 3), dtype=np.uint8))
    trace = analysis.candle_detection_trace
    assert trace is not None
    final_by_id = {item.candidate_id: item for item in trace.final_candles}

    assert final_by_id["flag"].is_latest is False
    assert final_by_id["price_text"].is_latest is False


def test_candles_ids_and_dominant_width_reach_resolver_aligned() -> None:
    candles, candidate_ids = _available_input()
    resolver = _CapturingMembershipResolver()
    pipeline, _ = _pipeline(candles, candidate_ids, resolver=resolver)

    pipeline.analyze(np.zeros((10, 10, 3), dtype=np.uint8))

    assert resolver.received_candles == candles
    assert all(
        received is expected
        for received, expected in zip(
            resolver.received_candles or (),
            candles,
            strict=True,
        )
    )
    assert resolver.received_candidate_ids == candidate_ids
    assert resolver.received_dominant_width == 8.0


def test_ambiguous_membership_produces_empty_unknown_series() -> None:
    left, left_ids = _series(4, start_x=0, prefix="left")
    right, right_ids = _series(4, start_x=100, start_y=180, prefix="right")
    pipeline, builder = _pipeline(left + right, left_ids + right_ids)

    analysis = pipeline.analyze(np.zeros((10, 10, 3), dtype=np.uint8))

    assert builder.received == ()
    assert analysis.series.is_empty()
    assert analysis.series.latest is None
    assert analysis.trend is TrendDirection.UNKNOWN
    assert analysis.candle_detection_trace is not None
    assert analysis.candle_detection_trace.series_membership is not None
    assert analysis.candle_detection_trace.series_membership.status is (
        CandleSeriesMembershipStatus.AMBIGUOUS
    )


def test_insufficient_membership_produces_empty_unknown_series() -> None:
    candles, candidate_ids = _series(3)
    pipeline, builder = _pipeline(candles, candidate_ids)

    analysis = pipeline.analyze(np.zeros((10, 10, 3), dtype=np.uint8))

    assert builder.received == ()
    assert analysis.series.is_empty()
    assert analysis.trend is TrendDirection.UNKNOWN
    assert analysis.candle_detection_trace is not None
    assert analysis.candle_detection_trace.series_membership is not None
    assert analysis.candle_detection_trace.series_membership.status is (
        CandleSeriesMembershipStatus.INSUFFICIENT_SUPPORT
    )


def test_unavailable_membership_never_falls_back_to_rightmost_candidate() -> None:
    candles, candidate_ids = _series(3)
    pipeline, _ = _pipeline(candles, candidate_ids)

    analysis = pipeline.analyze(np.zeros((10, 10, 3), dtype=np.uint8))
    trace = analysis.candle_detection_trace
    assert trace is not None

    assert analysis.series.latest is None
    assert all(not candle.is_latest for candle in trace.final_candles)
    assert trace.final_candles[-1].candidate_id == candidate_ids[-1]


def test_unavailable_membership_degrades_reference_and_indicators_safely() -> None:
    candles, candidate_ids = _series(3)
    pipeline, _ = _pipeline(candles, candidate_ids)
    analysis = pipeline.analyze(np.zeros((10, 10, 3), dtype=np.uint8))

    reference = VisualStrategySignalAnalysisPipeline._price_reference_result(analysis)
    indicators = VisualIndicatorSnapshotBuilder().build(
        analysis.series,
        StrategyProfile.otc_precision_10s(),
    )

    assert reference.status is VisualPriceReferenceStatus.LATEST_CANDLE_MISSING
    assert reference.reference is None
    assert indicators is None
