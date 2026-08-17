from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import numpy as np

from pocket_option_analyzer.application.evidence import (
    VisualEvidenceAssociation,
    VisualEvidencePhase,
    VisualEvidenceRecorder,
    VisualFrameEvidence,
)
from pocket_option_analyzer.application.signals import (
    SignalRecorder,
    VisualSignalRecordingPipeline,
)
from pocket_option_analyzer.application.strategy import (
    StrategyObservationOutcome,
    StrategyObservationRecorder,
    StrategyObservationResolution,
    StrategyObservationResolutionBatch,
    VisualPriceReference,
    VisualPriceReferenceResult,
    VisualPriceReferenceStatus,
    VisualReferenceMovement,
    VisualReferenceResolution,
)
from pocket_option_analyzer.application.use_cases import (
    AnalyzeCapturedFrameUseCase,
    FrameAnalysisLoopService,
)
from pocket_option_analyzer.domain.signals import (
    MarketSignal,
    SignalDirection,
    SignalHistory,
    SignalRecord,
    SignalStrength,
)
from pocket_option_analyzer.infrastructure.capture.models import Frame
from pocket_option_analyzer.infrastructure.evidence import (
    FilesystemVisualEvidenceRecorder,
)
from pocket_option_analyzer.vision.models import (
    CandleDetectionTrace,
    CandleSeries,
    ChartRegion,
    CurrentVisualPriceDetectionTrace,
    CurrentVisualPriceExtraction,
    CurrentVisualPriceRejectionCounts,
    CurrentVisualPriceStatus,
    MarketAnalysis,
    TrendDirection,
)

_ANCHORS = (
    ("bullish", 1.0, 0.8, 0.6, 0.4),
    ("bearish", 0.7, 0.5, 0.3, 0.0),
)


def _instant(seconds: int = 0) -> datetime:
    return datetime(2026, 8, 17, 12, 0, seconds, tzinfo=UTC)


def _reference(value: float) -> VisualPriceReference:
    return VisualPriceReference(value=value, anchor_shape=_ANCHORS)


def _reference_result(value: float = 100.0) -> VisualPriceReferenceResult:
    return VisualPriceReferenceResult(
        reference=_reference(value),
        status=VisualPriceReferenceStatus.OK,
        anchor_count=2,
        latest_candidate_x=100,
        latest_candidate_y=200,
        close_roi_y=210,
        anchor_top_roi_y=100,
        anchor_bottom_roi_y=300,
        raw_normalized_close=0.45,
    )


def _current_price() -> CurrentVisualPriceExtraction:
    return CurrentVisualPriceExtraction(
        price=None,
        status=CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE,
        diagnostic="diagnostic extraction",
    )


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


def _market_analysis(
    *,
    chart_region: ChartRegion | None = None,
    price_region: ChartRegion | None = None,
) -> MarketAnalysis:
    return MarketAnalysis(
        series=CandleSeries(candles=()),
        trend=TrendDirection.UNKNOWN,
        current_visual_price=_current_price(),
        chart_region=chart_region,
        price_observation_region=price_region,
        candle_detection_trace=_candle_trace(),
        current_visual_price_detection_trace=_price_trace(),
    )


def _observation(
    snapshot_started_at: datetime,
    *,
    observed_at: datetime | None = None,
    direction: SignalDirection | None = SignalDirection.CALL,
) -> SimpleNamespace:
    observed = observed_at or snapshot_started_at
    reference_result = _reference_result()
    return SimpleNamespace(
        candle_interval_started_at=snapshot_started_at,
        observed_at=observed,
        resolve_at=observed + timedelta(seconds=10),
        direction=direction,
        entry_reference=reference_result.reference,
        entry_reference_result=reference_result,
        current_visual_price=None,
        visual_price_comparison_context=None,
    )


def _primary_resolution(
    snapshot_started_at: datetime,
    *,
    resolved_at: datetime,
) -> StrategyObservationResolution:
    return StrategyObservationResolution(
        snapshot_id=snapshot_started_at.isoformat(),
        observed_at=snapshot_started_at,
        resolve_at=snapshot_started_at + timedelta(seconds=10),
        resolved_at=resolved_at,
        direction=SignalDirection.CALL,
        entry_reference=_reference(100.0),
        exit_reference=_reference(101.0),
        outcome=StrategyObservationOutcome.WIN,
    )


def _reference_resolution(
    snapshot_started_at: datetime,
    *,
    resolved_at: datetime,
) -> VisualReferenceResolution:
    return VisualReferenceResolution(
        snapshot_id=snapshot_started_at.isoformat(),
        observed_at=snapshot_started_at,
        resolve_at=snapshot_started_at + timedelta(seconds=10),
        resolved_at=resolved_at,
        entry_reference=_reference(100.0),
        exit_reference=_reference(101.0),
        movement=VisualReferenceMovement.UP,
    )


class _AnalysisPipeline:
    def __init__(
        self,
        *,
        observation: object | None = None,
        market_analysis: MarketAnalysis | None = None,
        reference_result: VisualPriceReferenceResult | None = None,
    ) -> None:
        self.observation = observation
        self.last_market_analysis = market_analysis
        self.last_current_visual_price = (
            market_analysis.current_visual_price
            if market_analysis is not None
            else None
        )
        self.last_price_reference_result = reference_result
        self.last_price_reference = (
            reference_result.reference if reference_result is not None else None
        )
        self.last_visual_price_comparison_context = None

    def analyze(
        self,
        image,
        price_observation_image=None,
        chart_region=None,
        price_observation_region=None,
    ) -> MarketSignal:
        return MarketSignal(
            direction=SignalDirection.CALL,
            strength=SignalStrength.HIGH,
            reason="evidence association test",
        )

    def build_last_observation(self, observed_at: datetime):
        return self.observation


class _ObservationRecorder:
    def __init__(
        self,
        *,
        batches: list[StrategyObservationResolutionBatch] | None = None,
        accepted: list[bool] | None = None,
    ) -> None:
        self._batches = list(batches or [])
        self._accepted = list(accepted or [])
        self.resolve_calls = 0
        self.report_calls = 0
        self.record_calls = 0

    def resolve_due(self, **kwargs):
        self.resolve_calls += 1
        return ()

    def resolve_due_with_report(self, **kwargs):
        self.report_calls += 1
        if self._batches:
            return self._batches.pop(0)
        return StrategyObservationResolutionBatch((), ())

    def record(self, observation) -> bool:
        self.record_calls += 1
        if self._accepted:
            return self._accepted.pop(0)
        return True


class _EvidenceRecorder:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[
            tuple[VisualFrameEvidence, tuple[VisualEvidenceAssociation, ...]]
        ] = []

    def record_frame(
        self,
        frame_evidence: VisualFrameEvidence,
        associations: tuple[VisualEvidenceAssociation, ...],
    ) -> None:
        self.calls.append((frame_evidence, associations))
        if self.fail:
            raise OSError("evidence store unavailable")


class _SignalWriter:
    def __init__(self) -> None:
        self.records: list[SignalRecord] = []

    def write(self, record: SignalRecord) -> None:
        self.records.append(record)


class _StrategyWriter:
    def __init__(self) -> None:
        self.observations: list[object] = []
        self.resolutions: list[StrategyObservationResolution] = []
        self.reference_validations: list[object] = []
        self.reference_resolutions: list[VisualReferenceResolution] = []

    def write(self, observation: object) -> None:
        self.observations.append(observation)

    def write_resolution(self, resolution: StrategyObservationResolution) -> None:
        self.resolutions.append(resolution)

    def write_reference_validation(self, validation: object) -> None:
        self.reference_validations.append(validation)

    def write_reference_resolution(
        self,
        resolution: VisualReferenceResolution,
    ) -> None:
        self.reference_resolutions.append(resolution)


def _pipeline(
    *,
    analysis: _AnalysisPipeline,
    observation_recorder,
    evidence_recorder: VisualEvidenceRecorder | None,
    signal_writer: _SignalWriter | None = None,
) -> VisualSignalRecordingPipeline:
    return VisualSignalRecordingPipeline(
        analysis_pipeline=analysis,
        recorder=SignalRecorder(SignalHistory()),
        record_writer=signal_writer,
        observation_recorder=observation_recorder,
        visual_evidence_recorder=evidence_recorder,
    )


def test_disabled_evidence_recorder_preserves_legacy_resolution_path() -> None:
    observation_recorder = _ObservationRecorder()
    pipeline = _pipeline(
        analysis=_AnalysisPipeline(),
        observation_recorder=observation_recorder,
        evidence_recorder=None,
    )

    record = pipeline.analyze_and_record(
        image=np.zeros((10, 10, 4), dtype=np.uint8),
        frame_id=1,
        created_at=_instant(),
    )

    assert record.signal.direction is SignalDirection.CALL
    assert observation_recorder.resolve_calls == 1
    assert observation_recorder.report_calls == 0


def test_entry_evidence_uses_accepted_observation_and_exact_frame_data() -> None:
    snapshot_started_at = _instant()
    observed_at = _instant(1)
    observation = _observation(snapshot_started_at, observed_at=observed_at)
    chart_region = ChartRegion(x=10, y=20, width=100, height=80)
    price_region = ChartRegion(x=30, y=40, width=100, height=20)
    market_analysis = _market_analysis(
        chart_region=chart_region,
        price_region=price_region,
    )
    reference_result = _reference_result()
    evidence_recorder = _EvidenceRecorder()
    image = np.zeros((80, 100, 4), dtype=np.uint8)
    price_image = np.zeros((20, 100, 4), dtype=np.uint8)
    pipeline = _pipeline(
        analysis=_AnalysisPipeline(
            observation=observation,
            market_analysis=market_analysis,
            reference_result=reference_result,
        ),
        observation_recorder=_ObservationRecorder(accepted=[True]),
        evidence_recorder=evidence_recorder,
    )

    pipeline.analyze_and_record(
        image=image,
        price_observation_image=price_image,
        chart_region=chart_region,
        price_observation_region=price_region,
        frame_id=17,
        created_at=observed_at,
        source="captured_frame_visual_analysis",
    )

    assert len(evidence_recorder.calls) == 1
    evidence, associations = evidence_recorder.calls[0]
    assert evidence.frame_id == 17
    assert evidence.frame_timestamp is observed_at
    assert evidence.image is image
    assert evidence.price_observation_image is price_image
    assert evidence.chart_region is chart_region
    assert evidence.price_observation_region is price_region
    assert evidence.market_analysis is market_analysis
    assert evidence.current_visual_price is market_analysis.current_visual_price
    assert evidence.visual_price_reference_result is reference_result
    assert evidence.candle_detection_trace is market_analysis.candle_detection_trace
    assert (
        evidence.current_visual_price_detection_trace
        is market_analysis.current_visual_price_detection_trace
    )
    assert associations == (
        VisualEvidenceAssociation(
            snapshot_id=snapshot_started_at.isoformat(),
            phase=VisualEvidencePhase.ENTRY,
            observed_at=observed_at,
            resolve_at=observation.resolve_at,
            candle_interval_started_at=snapshot_started_at,
        ),
    )


def test_duplicate_observation_does_not_create_second_entry_association() -> None:
    observation = _observation(_instant())
    evidence_recorder = _EvidenceRecorder()
    observation_recorder = _ObservationRecorder(accepted=[True, False])
    pipeline = _pipeline(
        analysis=_AnalysisPipeline(
            observation=observation,
            reference_result=_reference_result(),
        ),
        observation_recorder=observation_recorder,
        evidence_recorder=evidence_recorder,
    )

    for frame_id in (1, 2):
        pipeline.analyze_and_record(
            image=np.zeros((10, 10, 4), dtype=np.uint8),
            frame_id=frame_id,
            created_at=_instant(),
        )

    assert len(evidence_recorder.calls) == 1
    assert evidence_recorder.calls[0][0].frame_id == 1
    assert observation_recorder.record_calls == 2


def test_reference_only_resolution_creates_exit_association() -> None:
    snapshot = _instant()
    resolved_at = _instant(10)
    reference_resolution = _reference_resolution(
        snapshot,
        resolved_at=resolved_at,
    )
    evidence_recorder = _EvidenceRecorder()
    pipeline = _pipeline(
        analysis=_AnalysisPipeline(reference_result=_reference_result(101.0)),
        observation_recorder=_ObservationRecorder(
            batches=[
                StrategyObservationResolutionBatch(
                    resolutions=(),
                    reference_resolutions=(reference_resolution,),
                )
            ]
        ),
        evidence_recorder=evidence_recorder,
    )

    pipeline.analyze_and_record(
        image=np.zeros((10, 10, 4), dtype=np.uint8),
        frame_id=9,
        created_at=resolved_at,
    )

    _, associations = evidence_recorder.calls[0]
    assert associations[0].snapshot_id == snapshot.isoformat()
    assert associations[0].phase is VisualEvidencePhase.EXIT
    assert associations[0].resolved_at is resolved_at


def test_primary_and_reference_resolution_share_one_exit_association() -> None:
    snapshot = _instant()
    resolved_at = _instant(10)
    evidence_recorder = _EvidenceRecorder()
    pipeline = _pipeline(
        analysis=_AnalysisPipeline(reference_result=_reference_result(101.0)),
        observation_recorder=_ObservationRecorder(
            batches=[
                StrategyObservationResolutionBatch(
                    resolutions=(
                        _primary_resolution(snapshot, resolved_at=resolved_at),
                    ),
                    reference_resolutions=(
                        _reference_resolution(snapshot, resolved_at=resolved_at),
                    ),
                )
            ]
        ),
        evidence_recorder=evidence_recorder,
    )

    pipeline.analyze_and_record(
        image=np.zeros((10, 10, 4), dtype=np.uint8),
        frame_id=10,
        created_at=resolved_at,
    )

    assert len(evidence_recorder.calls[0][1]) == 1
    assert evidence_recorder.calls[0][1][0].phase is VisualEvidencePhase.EXIT


def test_multiple_due_snapshots_share_single_frame_evidence_instance() -> None:
    first = _instant()
    second = first + timedelta(seconds=1)
    third = first + timedelta(seconds=2)
    resolved_at = _instant(12)
    evidence_recorder = _EvidenceRecorder()
    batch = StrategyObservationResolutionBatch(
        resolutions=(_primary_resolution(first, resolved_at=resolved_at),),
        reference_resolutions=(
            _reference_resolution(first, resolved_at=resolved_at),
            _reference_resolution(second, resolved_at=resolved_at),
            _reference_resolution(third, resolved_at=resolved_at),
        ),
    )
    pipeline = _pipeline(
        analysis=_AnalysisPipeline(reference_result=_reference_result(101.0)),
        observation_recorder=_ObservationRecorder(batches=[batch]),
        evidence_recorder=evidence_recorder,
    )

    pipeline.analyze_and_record(
        image=np.zeros((10, 10, 4), dtype=np.uint8),
        frame_id=11,
        created_at=resolved_at,
    )

    assert len(evidence_recorder.calls) == 1
    evidence, associations = evidence_recorder.calls[0]
    expanded_frames = tuple(evidence for _ in associations)
    assert len(associations) == 3
    assert all(frame is evidence for frame in expanded_frames)
    assert {association.snapshot_id for association in associations} == {
        first.isoformat(),
        second.isoformat(),
        third.isoformat(),
    }


def test_same_frame_consolidates_exit_and_entry_associations() -> None:
    exit_snapshot = _instant()
    entry_snapshot = _instant(10)
    observation = _observation(entry_snapshot)
    resolved_at = _instant(10)
    evidence_recorder = _EvidenceRecorder()
    pipeline = _pipeline(
        analysis=_AnalysisPipeline(
            observation=observation,
            reference_result=_reference_result(101.0),
        ),
        observation_recorder=_ObservationRecorder(
            batches=[
                StrategyObservationResolutionBatch(
                    resolutions=(
                        _primary_resolution(
                            exit_snapshot,
                            resolved_at=resolved_at,
                        ),
                    ),
                    reference_resolutions=(),
                )
            ],
            accepted=[True],
        ),
        evidence_recorder=evidence_recorder,
    )

    pipeline.analyze_and_record(
        image=np.zeros((10, 10, 4), dtype=np.uint8),
        frame_id=12,
        created_at=resolved_at,
    )

    assert len(evidence_recorder.calls) == 1
    evidence, associations = evidence_recorder.calls[0]
    assert [association.phase for association in associations] == [
        VisualEvidencePhase.EXIT,
        VisualEvidencePhase.ENTRY,
    ]
    assert [association.snapshot_id for association in associations] == [
        exit_snapshot.isoformat(),
        entry_snapshot.isoformat(),
    ]
    assert all(evidence is evidence_recorder.calls[0][0] for _ in associations)


def test_different_frames_keep_different_deterministic_identities() -> None:
    evidence_recorder = _EvidenceRecorder()
    observation_recorder = _ObservationRecorder(accepted=[True, True])
    analysis = _AnalysisPipeline(reference_result=_reference_result())
    pipeline = _pipeline(
        analysis=analysis,
        observation_recorder=observation_recorder,
        evidence_recorder=evidence_recorder,
    )
    for frame_id, snapshot in ((31, _instant()), (32, _instant(1))):
        analysis.observation = _observation(snapshot)
        pipeline.analyze_and_record(
            image=np.zeros((10, 10, 4), dtype=np.uint8),
            frame_id=frame_id,
            created_at=snapshot,
        )

    assert [call[0].frame_id for call in evidence_recorder.calls] == [31, 32]
    assert evidence_recorder.calls[0][0] is not evidence_recorder.calls[1][0]


def test_legacy_analysis_without_traces_still_records_evidence() -> None:
    evidence_recorder = _EvidenceRecorder()
    pipeline = _pipeline(
        analysis=_AnalysisPipeline(
            observation=_observation(_instant()),
            market_analysis=None,
            reference_result=_reference_result(),
        ),
        observation_recorder=_ObservationRecorder(accepted=[True]),
        evidence_recorder=evidence_recorder,
    )

    pipeline.analyze_and_record(
        image=np.zeros((10, 10, 4), dtype=np.uint8),
        frame_id=40,
        created_at=_instant(),
    )

    evidence = evidence_recorder.calls[0][0]
    assert evidence.market_analysis is None
    assert evidence.candle_detection_trace is None
    assert evidence.current_visual_price_detection_trace is None


@dataclass(slots=True)
class _CaptureOnce:
    frame: Frame
    calls: int = 0

    def capture_once(self) -> Frame:
        self.calls += 1
        return self.frame


def test_loop_captures_once_and_evidence_keeps_exact_captured_arrays() -> None:
    image = np.zeros((80, 100, 4), dtype=np.uint8)
    price_image = np.zeros((20, 100, 4), dtype=np.uint8)
    frame = Frame(
        frame_id=51,
        timestamp=_instant(),
        image=image,
        price_observation_image=price_image,
    )
    capture = _CaptureOnce(frame)
    evidence_recorder = _EvidenceRecorder()
    pipeline = _pipeline(
        analysis=_AnalysisPipeline(
            observation=_observation(_instant()),
            reference_result=_reference_result(),
        ),
        observation_recorder=_ObservationRecorder(accepted=[True]),
        evidence_recorder=evidence_recorder,
    )
    service = FrameAnalysisLoopService(
        capture_service=capture,
        analysis_use_case=AnalyzeCapturedFrameUseCase(pipeline=pipeline),
    )

    service.run_once()

    evidence = evidence_recorder.calls[0][0]
    assert capture.calls == 1
    assert evidence.frame_id == frame.frame_id
    assert evidence.image is frame.image
    assert evidence.price_observation_image is frame.price_observation_image


def test_evidence_failure_does_not_change_resolution_pending_or_writers() -> None:
    snapshot = _instant()
    entry_analysis = _AnalysisPipeline(
        observation=_observation(snapshot),
        reference_result=_reference_result(100.0),
    )
    strategy_writer = _StrategyWriter()
    signal_writer = _SignalWriter()
    strategy_recorder = StrategyObservationRecorder(writer=strategy_writer)
    failing_evidence = _EvidenceRecorder(fail=True)
    pipeline = _pipeline(
        analysis=entry_analysis,
        observation_recorder=strategy_recorder,
        evidence_recorder=failing_evidence,
        signal_writer=signal_writer,
    )

    pipeline.analyze_and_record(
        image=np.zeros((10, 10, 4), dtype=np.uint8),
        frame_id=61,
        created_at=snapshot,
    )
    entry_analysis.observation = None
    entry_analysis.last_price_reference_result = _reference_result(101.0)
    entry_analysis.last_price_reference = (
        entry_analysis.last_price_reference_result.reference
    )
    pipeline.analyze_and_record(
        image=np.zeros((10, 10, 4), dtype=np.uint8),
        frame_id=62,
        created_at=snapshot + timedelta(seconds=10),
    )

    assert len(strategy_writer.observations) == 1
    assert len(strategy_writer.resolutions) == 1
    assert strategy_writer.resolutions[0].outcome is StrategyObservationOutcome.WIN
    assert len(strategy_writer.reference_resolutions) == 1
    assert len(signal_writer.records) == 2
    assert len(failing_evidence.calls) == 2

    after_failure = strategy_recorder.resolve_due_with_report(
        observed_at=snapshot + timedelta(seconds=11),
        exit_reference=_reference(102.0),
    )
    assert after_failure.resolutions == ()
    assert after_failure.reference_resolutions == ()


def _run_functional_sequence(
    evidence_recorder: VisualEvidenceRecorder | None,
) -> _StrategyWriter:
    snapshot = _instant()
    writer = _StrategyWriter()
    recorder = StrategyObservationRecorder(writer=writer)
    analysis = _AnalysisPipeline(
        observation=_observation(snapshot),
        reference_result=_reference_result(100.0),
    )
    pipeline = _pipeline(
        analysis=analysis,
        observation_recorder=recorder,
        evidence_recorder=evidence_recorder,
    )
    pipeline.analyze_and_record(
        image=np.zeros((10, 10, 4), dtype=np.uint8),
        frame_id=71,
        created_at=snapshot,
    )
    analysis.observation = None
    analysis.last_price_reference_result = _reference_result(101.0)
    analysis.last_price_reference = analysis.last_price_reference_result.reference
    pipeline.analyze_and_record(
        image=np.zeros((10, 10, 4), dtype=np.uint8),
        frame_id=72,
        created_at=snapshot + timedelta(seconds=10),
    )
    return writer


def test_fake_evidence_recorder_is_functionally_invariant_to_disabled() -> None:
    disabled = _run_functional_sequence(None)
    enabled = _run_functional_sequence(_EvidenceRecorder())

    assert enabled.observations == disabled.observations
    assert enabled.reference_validations == disabled.reference_validations
    assert enabled.resolutions == disabled.resolutions
    assert enabled.reference_resolutions == disabled.reference_resolutions
    assert enabled.resolutions[0].outcome is StrategyObservationOutcome.WIN
    assert (
        enabled.resolutions[0].visual_price_comparison
        == disabled.resolutions[0].visual_price_comparison
    )
    assert (
        enabled.resolutions[0].visual_price_movement_classification
        == disabled.resolutions[0].visual_price_movement_classification
    )


def test_filesystem_evidence_recorder_is_functionally_invariant_to_disabled(
    tmp_path,
) -> None:
    disabled = _run_functional_sequence(None)
    enabled = _run_functional_sequence(
        FilesystemVisualEvidenceRecorder(tmp_path / "evidence")
    )

    assert enabled.observations == disabled.observations
    assert enabled.reference_validations == disabled.reference_validations
    assert enabled.resolutions == disabled.resolutions
    assert enabled.reference_resolutions == disabled.reference_resolutions
    assert enabled.resolutions[0].outcome is StrategyObservationOutcome.WIN
    assert (
        enabled.resolutions[0].visual_price_comparison
        == disabled.resolutions[0].visual_price_comparison
    )
    assert (
        enabled.resolutions[0].visual_price_movement_classification
        == disabled.resolutions[0].visual_price_movement_classification
    )


def test_filesystem_evidence_error_is_fail_soft(
    tmp_path,
    monkeypatch,
) -> None:
    recorder = FilesystemVisualEvidenceRecorder(tmp_path / "evidence")

    def fail_record_frame(frame_evidence, associations) -> None:
        raise OSError("filesystem evidence failed")

    monkeypatch.setattr(recorder, "record_frame", fail_record_frame)

    writer = _run_functional_sequence(recorder)

    assert len(writer.observations) == 1
    assert len(writer.resolutions) == 1
    assert writer.resolutions[0].outcome is StrategyObservationOutcome.WIN
    assert len(writer.reference_resolutions) == 1


def test_loop_with_filesystem_store_captures_once_per_tick(tmp_path) -> None:
    image = np.zeros((80, 100, 4), dtype=np.uint8)
    price_image = np.zeros((20, 100, 4), dtype=np.uint8)
    frame = Frame(
        frame_id=81,
        timestamp=_instant(),
        image=image,
        price_observation_image=price_image,
    )
    capture = _CaptureOnce(frame)
    pipeline = _pipeline(
        analysis=_AnalysisPipeline(
            observation=_observation(_instant()),
            reference_result=_reference_result(),
        ),
        observation_recorder=_ObservationRecorder(accepted=[True]),
        evidence_recorder=FilesystemVisualEvidenceRecorder(
            tmp_path / "evidence"
        ),
    )
    service = FrameAnalysisLoopService(
        capture_service=capture,
        analysis_use_case=AnalyzeCapturedFrameUseCase(pipeline=pipeline),
    )

    service.run_once()

    assert capture.calls == 1
    assert len(list((tmp_path / "evidence" / "frames").iterdir())) == 1
