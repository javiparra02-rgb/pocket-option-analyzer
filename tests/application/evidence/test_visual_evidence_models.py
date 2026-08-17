from datetime import UTC, datetime, timedelta
from typing import get_type_hints

import numpy as np
import pytest

from pocket_option_analyzer.application.evidence import (
    VisualEvidenceAssociation,
    VisualEvidencePhase,
    VisualEvidenceRecorder,
    VisualFrameEvidence,
)
from pocket_option_analyzer.application.signals import VisualSignalRecordingPipeline
from pocket_option_analyzer.application.strategy import (
    StrategyObservationRecorder,
    VisualPriceReferenceResult,
    VisualPriceReferenceStatus,
)
from pocket_option_analyzer.application.use_cases import AnalyzeCapturedFrameUseCase
from pocket_option_analyzer.vision.models import (
    CandleDetectionTrace,
    CandleSeries,
    CurrentVisualPriceDetectionTrace,
    CurrentVisualPriceExtraction,
    CurrentVisualPriceRejectionCounts,
    CurrentVisualPriceStatus,
    MarketAnalysis,
    TrendDirection,
)


def _instant() -> datetime:
    return datetime(2026, 8, 17, 12, 0, tzinfo=UTC)


def _candle_trace() -> CandleDetectionTrace:
    return CandleDetectionTrace(
        candidates=(),
        merges=(),
        returned_candidate_ids=(),
        dominant_width=None,
        maximum_returned_candidates=60,
    )


def _price_trace() -> CurrentVisualPriceDetectionTrace:
    return CurrentVisualPriceDetectionTrace(
        status=CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE,
        image_width=None,
        image_height=None,
        effective_chart_right_x=None,
        effective_chart_right_source=None,
        band_start=None,
        band_end=None,
        band_width=None,
        safe_top=None,
        safe_bottom=None,
        masked_pixel_count=0,
        candidates=(),
        rejection_counts=CurrentVisualPriceRejectionCounts(),
    )


def _frame_evidence() -> VisualFrameEvidence:
    candle_trace = _candle_trace()
    price_trace = _price_trace()
    extraction = CurrentVisualPriceExtraction(
        price=None,
        status=CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE,
    )
    analysis = MarketAnalysis(
        series=CandleSeries(candles=()),
        trend=TrendDirection.UNKNOWN,
        current_visual_price=extraction,
        candle_detection_trace=candle_trace,
        current_visual_price_detection_trace=price_trace,
    )
    return VisualFrameEvidence(
        frame_id=7,
        frame_timestamp=_instant(),
        image=np.zeros((80, 100, 4), dtype=np.uint8),
        price_observation_image=np.zeros((20, 100, 4), dtype=np.uint8),
        chart_region=None,
        price_observation_region=None,
        source="test_capture",
        market_analysis=analysis,
        current_visual_price=extraction,
        visual_price_reference_result=VisualPriceReferenceResult(
            reference=None,
            status=VisualPriceReferenceStatus.LATEST_CANDLE_MISSING,
        ),
        candle_detection_trace=candle_trace,
        current_visual_price_detection_trace=price_trace,
    )


def test_entry_association_preserves_canonical_snapshot_and_timestamps() -> None:
    observed_at = _instant()
    resolve_at = observed_at + timedelta(seconds=10)

    association = VisualEvidenceAssociation(
        snapshot_id="2026-08-17T11:59:50+00:00",
        phase=VisualEvidencePhase.ENTRY,
        observed_at=observed_at,
        resolve_at=resolve_at,
        candle_interval_started_at=(observed_at - timedelta(seconds=10)),
    )

    assert association.snapshot_id == "2026-08-17T11:59:50+00:00"
    assert association.observed_at is observed_at
    assert association.resolve_at is resolve_at
    assert association.resolved_at is None


def test_exit_association_requires_resolved_at() -> None:
    with pytest.raises(ValueError, match="requires resolved_at"):
        VisualEvidenceAssociation(
            snapshot_id=_instant().isoformat(),
            phase=VisualEvidencePhase.EXIT,
            observed_at=_instant(),
            resolve_at=_instant(),
        )


def test_entry_association_rejects_resolved_at() -> None:
    with pytest.raises(ValueError, match="cannot include resolved_at"):
        VisualEvidenceAssociation(
            snapshot_id=_instant().isoformat(),
            phase=VisualEvidencePhase.ENTRY,
            observed_at=_instant(),
            resolve_at=_instant(),
            candle_interval_started_at=_instant(),
            resolved_at=_instant(),
        )


@pytest.mark.parametrize("snapshot_id", ["", "   "])
def test_association_rejects_empty_snapshot_id(snapshot_id: str) -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        VisualEvidenceAssociation(
            snapshot_id=snapshot_id,
            phase=VisualEvidencePhase.ENTRY,
            observed_at=_instant(),
            resolve_at=_instant(),
            candle_interval_started_at=_instant(),
        )


def test_entry_association_requires_candle_interval_timestamp() -> None:
    with pytest.raises(ValueError, match="candle_interval_started_at"):
        VisualEvidenceAssociation(
            snapshot_id=_instant().isoformat(),
            phase=VisualEvidencePhase.ENTRY,
            observed_at=_instant(),
            resolve_at=_instant(),
        )


def test_frame_evidence_borrows_arrays_and_exposes_dimensions() -> None:
    evidence = _frame_evidence()
    image = evidence.image
    price_image = evidence.price_observation_image

    assert evidence.image is image
    assert evidence.price_observation_image is price_image
    assert evidence.image_shape == (80, 100, 4)
    assert evidence.price_observation_image_shape == (20, 100, 4)

    image[0, 0, 0] = 255
    assert evidence.image[0, 0, 0] == 255


def test_frame_evidence_keeps_analysis_objects_by_identity() -> None:
    evidence = _frame_evidence()
    analysis = evidence.market_analysis

    assert analysis is not None
    assert evidence.current_visual_price is analysis.current_visual_price
    assert evidence.candle_detection_trace is analysis.candle_detection_trace
    assert (
        evidence.current_visual_price_detection_trace
        is analysis.current_visual_price_detection_trace
    )


def test_frame_evidence_rejects_diagnostics_from_another_analysis() -> None:
    evidence = _frame_evidence()

    with pytest.raises(ValueError, match="same MarketAnalysis"):
        VisualFrameEvidence(
            frame_id=evidence.frame_id,
            frame_timestamp=evidence.frame_timestamp,
            image=evidence.image,
            price_observation_image=evidence.price_observation_image,
            chart_region=None,
            price_observation_region=None,
            source=evidence.source,
            market_analysis=evidence.market_analysis,
            current_visual_price=evidence.current_visual_price,
            visual_price_reference_result=(
                evidence.visual_price_reference_result
            ),
            candle_detection_trace=_candle_trace(),
            current_visual_price_detection_trace=(
                evidence.current_visual_price_detection_trace
            ),
        )


def test_new_public_evidence_contracts_resolve_runtime_type_hints() -> None:
    assert get_type_hints(VisualEvidenceAssociation)
    assert get_type_hints(VisualFrameEvidence)
    assert get_type_hints(VisualEvidenceRecorder.record_frame)
    assert get_type_hints(VisualSignalRecordingPipeline.__init__)
    assert get_type_hints(VisualSignalRecordingPipeline.analyze_and_record)
    assert get_type_hints(StrategyObservationRecorder.resolve_due_with_report)
    assert get_type_hints(AnalyzeCapturedFrameUseCase.execute)
