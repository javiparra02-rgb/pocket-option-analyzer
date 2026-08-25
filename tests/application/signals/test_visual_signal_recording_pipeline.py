from datetime import UTC, datetime
from types import SimpleNamespace

import numpy as np

from pocket_option_analyzer.application.signals import (
    SignalRecorder,
    VisualSignalRecordingPipeline,
)
from pocket_option_analyzer.application.strategy import (
    CurrentVisualPriceComparisonContext,
    VisualPriceReferenceResult,
    VisualPriceReferenceStatus,
)
from pocket_option_analyzer.domain.signals import (
    MarketSignal,
    SignalDirection,
    SignalHistory,
    SignalRecord,
    SignalRecordDisposition,
    SignalStrength,
)
from pocket_option_analyzer.vision.models import (
    ChartRegion,
    CurrentVisualPrice,
    CurrentVisualPriceExtraction,
    CurrentVisualPriceStatus,
)


class FakeVisualStrategySignalAnalysisPipeline:
    def __init__(self) -> None:
        self.received_image = None
        self.received_price_observation_image = None
        self.received_chart_region = None
        self.received_price_observation_region = None
        self.last_price_reference = None
        self.last_current_visual_price = None
        self.last_visual_price_comparison_context = None
        self.last_current_candle_identity_resolution = None
        self.last_current_candle_identity_frame_context = None
        self.last_market_analysis = None
        self.last_price_reference_result = None
        self.received_frame_id = None
        self.received_frame_timestamp = None
        self.received_monotonic_timestamp = None
        self.received_source_key = None
        self.received_session_key = None
        self.started_sessions: list[str] = []
        self.stop_session_calls = 0

    def start_session(self, *, session_key: str) -> None:
        self.started_sessions.append(session_key)

    def stop_session(self) -> None:
        self.stop_session_calls += 1

    def analyze(
        self,
        image,
        price_observation_image=None,
        chart_region=None,
        price_observation_region=None,
        frame_id=None,
        frame_timestamp=None,
        monotonic_timestamp=None,
        source_key=None,
        session_key=None,
    ) -> MarketSignal:
        self.received_image = image
        self.received_price_observation_image = price_observation_image
        self.received_chart_region = chart_region
        self.received_price_observation_region = price_observation_region
        self.received_frame_id = frame_id
        self.received_frame_timestamp = frame_timestamp
        self.received_monotonic_timestamp = monotonic_timestamp
        self.received_source_key = source_key
        self.received_session_key = session_key
        return MarketSignal(
            direction=SignalDirection.CALL,
            strength=SignalStrength.HIGH,
            reason="Visual strategy conditions confirmed.",
        )

    def build_last_observation(self, observed_at):
        return None


class FakeObservationRecorder:
    def __init__(self) -> None:
        self.resolve_calls: list[dict[str, object]] = []

    def resolve_due(self, **kwargs):
        self.resolve_calls.append(kwargs)
        return ()

    def record(self, observation) -> bool:
        return True


class FakeIdentityEvidenceRecorder:
    def __init__(self, *, fail_record: bool = False) -> None:
        self.fail_record = fail_record
        self.started_sessions: list[str] = []
        self.stopped_sessions = 0
        self.frames = []

    def start_identity_session(self, *, session_key: str) -> None:
        self.started_sessions.append(session_key)

    def stop_identity_session(self) -> None:
        self.stopped_sessions += 1

    def record_identity_shadow(self, frame_evidence) -> None:
        if self.fail_record:
            raise OSError("identity evidence unavailable")
        self.frames.append(frame_evidence)


def _set_identity_same_pass(
    analysis_pipeline: FakeVisualStrategySignalAnalysisPipeline,
    *,
    frame_id: int,
    timestamp: datetime,
    status: str = "unavailable",
) -> tuple[SimpleNamespace, SimpleNamespace]:
    resolution = SimpleNamespace(
        trace=SimpleNamespace(
            frame_id=frame_id,
            wall_timestamp=timestamp,
            monotonic_timestamp=123.5,
            source_key="win32_hwnd:99",
            session_key="session-01",
            legacy_latest_candidate_id=None,
        ),
        result=SimpleNamespace(status=status),
    )
    frame_context = SimpleNamespace(
        frame_id=frame_id,
        wall_timestamp=timestamp,
        monotonic_timestamp=123.5,
        source_key="win32_hwnd:99",
        session_key="session-01",
        roi_width=100,
        roi_height=80,
        membership=None,
    )
    analysis_pipeline.last_current_candle_identity_resolution = resolution
    analysis_pipeline.last_current_candle_identity_frame_context = frame_context
    return resolution, frame_context


def test_analyze_and_record_propagates_price_observation_image_by_identity() -> None:
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    price_observation_image = np.zeros((20, 100, 3), dtype=np.uint8)
    analysis_pipeline = FakeVisualStrategySignalAnalysisPipeline()
    pipeline = VisualSignalRecordingPipeline(
        analysis_pipeline=analysis_pipeline,
        recorder=SignalRecorder(SignalHistory()),
    )

    pipeline.analyze_and_record(
        image=image,
        price_observation_image=price_observation_image,
    )

    assert analysis_pipeline.received_image is image
    assert analysis_pipeline.received_price_observation_image is (
        price_observation_image
    )


def test_analyze_and_record_propagates_capture_geometry_by_identity() -> None:
    chart_region = ChartRegion(x=10, y=20, width=100, height=80)
    price_region = ChartRegion(x=30, y=40, width=100, height=80)
    analysis_pipeline = FakeVisualStrategySignalAnalysisPipeline()
    pipeline = VisualSignalRecordingPipeline(
        analysis_pipeline=analysis_pipeline,
        recorder=SignalRecorder(SignalHistory()),
    )

    pipeline.analyze_and_record(
        image=np.zeros((80, 100, 3), dtype=np.uint8),
        chart_region=chart_region,
        price_observation_region=price_region,
    )

    assert analysis_pipeline.received_chart_region is chart_region
    assert analysis_pipeline.received_price_observation_region is price_region


def test_analyze_and_record_propagates_identity_runtime_metadata() -> None:
    analysis_pipeline = FakeVisualStrategySignalAnalysisPipeline()
    pipeline = VisualSignalRecordingPipeline(
        analysis_pipeline=analysis_pipeline,
        recorder=SignalRecorder(SignalHistory()),
    )
    created_at = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)

    pipeline.start_session(session_key="session-01")
    pipeline.analyze_and_record(
        image=np.zeros((80, 100, 3), dtype=np.uint8),
        created_at=created_at,
        frame_id=7,
        monotonic_timestamp=123.5,
        source_key="win32_hwnd:99",
        session_key="session-01",
    )
    pipeline.stop_session()

    assert analysis_pipeline.started_sessions == ["session-01"]
    assert analysis_pipeline.received_frame_id == 7
    assert analysis_pipeline.received_frame_timestamp is created_at
    assert analysis_pipeline.received_monotonic_timestamp == 123.5
    assert analysis_pipeline.received_source_key == "win32_hwnd:99"
    assert analysis_pipeline.received_session_key == "session-01"
    assert analysis_pipeline.stop_session_calls == 1


def test_identity_evidence_uses_atomic_same_pass_objects_without_reanalysis() -> None:
    timestamp = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)
    image = np.zeros((80, 100, 3), dtype=np.uint8)
    analysis_pipeline = FakeVisualStrategySignalAnalysisPipeline()
    resolution, frame_context = _set_identity_same_pass(
        analysis_pipeline,
        frame_id=7,
        timestamp=timestamp,
    )
    evidence_recorder = FakeIdentityEvidenceRecorder()
    pipeline = VisualSignalRecordingPipeline(
        analysis_pipeline=analysis_pipeline,
        recorder=SignalRecorder(SignalHistory()),
        identity_evidence_recorder=evidence_recorder,
    )

    pipeline.start_session(session_key="session-01")
    pipeline.analyze_and_record(
        image=image,
        created_at=timestamp,
        frame_id=7,
        monotonic_timestamp=123.5,
        source_key="win32_hwnd:99",
        session_key="session-01",
    )
    pipeline.stop_session()

    assert evidence_recorder.started_sessions == ["session-01"]
    assert evidence_recorder.stopped_sessions == 1
    assert len(evidence_recorder.frames) == 1
    persisted = evidence_recorder.frames[0]
    assert persisted.image is image
    assert persisted.resolution is resolution
    assert persisted.frame_context is frame_context
    assert analysis_pipeline.received_frame_id == 7


def test_identity_evidence_failure_does_not_change_legacy_signal() -> None:
    timestamp = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)
    baseline_analysis = FakeVisualStrategySignalAnalysisPipeline()
    _set_identity_same_pass(
        baseline_analysis,
        frame_id=7,
        timestamp=timestamp,
        status="missing_from_view",
    )
    baseline_pipeline = VisualSignalRecordingPipeline(
        analysis_pipeline=baseline_analysis,
        recorder=SignalRecorder(SignalHistory()),
    )
    baseline = baseline_pipeline.analyze_and_record(
        image=np.zeros((80, 100, 3), dtype=np.uint8),
        created_at=timestamp,
        frame_id=7,
        monotonic_timestamp=123.5,
        source_key="win32_hwnd:99",
        session_key="session-01",
    )
    analysis_pipeline = FakeVisualStrategySignalAnalysisPipeline()
    resolution, _ = _set_identity_same_pass(
        analysis_pipeline,
        frame_id=7,
        timestamp=timestamp,
        status="missing_from_view",
    )
    pipeline = VisualSignalRecordingPipeline(
        analysis_pipeline=analysis_pipeline,
        recorder=SignalRecorder(SignalHistory()),
        identity_evidence_recorder=FakeIdentityEvidenceRecorder(
            fail_record=True,
        ),
    )

    record = pipeline.analyze_and_record(
        image=np.zeros((80, 100, 3), dtype=np.uint8),
        created_at=timestamp,
        frame_id=7,
        monotonic_timestamp=123.5,
        source_key="win32_hwnd:99",
        session_key="session-01",
    )

    assert record.signal.direction is SignalDirection.CALL
    assert record.signal.strength is SignalStrength.HIGH
    assert record.signal == baseline.signal
    assert record.disposition is baseline.disposition
    assert analysis_pipeline.last_current_candle_identity_resolution is resolution


def test_missing_identity_with_persistence_does_not_gate_legacy_reference() -> None:
    timestamp = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)
    reference_result = VisualPriceReferenceResult(
        reference=None,
        status=VisualPriceReferenceStatus.LATEST_CANDLE_MISSING,
    )
    analysis_pipeline = FakeVisualStrategySignalAnalysisPipeline()
    analysis_pipeline.last_price_reference_result = reference_result
    _set_identity_same_pass(
        analysis_pipeline,
        frame_id=7,
        timestamp=timestamp,
        status="missing_from_view",
    )
    evidence_recorder = FakeIdentityEvidenceRecorder()
    pipeline = VisualSignalRecordingPipeline(
        analysis_pipeline=analysis_pipeline,
        recorder=SignalRecorder(SignalHistory()),
        identity_evidence_recorder=evidence_recorder,
    )

    record = pipeline.analyze_and_record(
        image=np.zeros((80, 100, 3), dtype=np.uint8),
        created_at=timestamp,
        frame_id=7,
        monotonic_timestamp=123.5,
        source_key="win32_hwnd:99",
        session_key="session-01",
    )

    assert record.signal.direction is SignalDirection.CALL
    assert analysis_pipeline.last_price_reference_result is reference_result
    assert len(evidence_recorder.frames) == 1


def test_analyze_and_record_propagates_exit_visual_price_by_identity() -> None:
    extraction = CurrentVisualPriceExtraction(
        price=CurrentVisualPrice(514.0, 0.73125, 1320, 800, "test", 0.92),
        status=CurrentVisualPriceStatus.OK,
        candidate_count=1,
        selected_x=1268.5,
        selected_y=514.0,
        confidence=0.92,
    )
    context = CurrentVisualPriceComparisonContext(
        current_visual_price=extraction,
        chart_region=ChartRegion(x=10, y=20, width=100, height=80),
        price_observation_region=ChartRegion(
            x=0,
            y=30,
            width=120,
            height=90,
        ),
        reference_result=VisualPriceReferenceResult(
            reference=None,
            status=VisualPriceReferenceStatus.LATEST_CANDLE_MISSING,
        ),
    )
    analysis_pipeline = FakeVisualStrategySignalAnalysisPipeline()
    analysis_pipeline.last_current_visual_price = extraction
    analysis_pipeline.last_visual_price_comparison_context = context
    observation_recorder = FakeObservationRecorder()
    created_at = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
    pipeline = VisualSignalRecordingPipeline(
        analysis_pipeline=analysis_pipeline,
        recorder=SignalRecorder(SignalHistory()),
        observation_recorder=observation_recorder,
    )

    pipeline.analyze_and_record(
        image=np.zeros((100, 100, 3), dtype=np.uint8),
        created_at=created_at,
    )

    assert observation_recorder.resolve_calls == [
        {
            "observed_at": created_at,
            "exit_reference": None,
            "exit_current_visual_price": extraction,
            "exit_visual_price_context": context,
        }
    ]
    assert context.current_visual_price is extraction


def test_analyze_and_record_propagates_exit_comparison_context_by_identity() -> None:
    context = CurrentVisualPriceComparisonContext(
        current_visual_price=None,
        chart_region=ChartRegion(x=10, y=20, width=100, height=80),
        price_observation_region=ChartRegion(
            x=0,
            y=30,
            width=120,
            height=90,
        ),
        reference_result=VisualPriceReferenceResult(
            reference=None,
            status=VisualPriceReferenceStatus.LATEST_CANDLE_MISSING,
        ),
    )
    analysis_pipeline = FakeVisualStrategySignalAnalysisPipeline()
    analysis_pipeline.last_visual_price_comparison_context = context
    observation_recorder = FakeObservationRecorder()
    created_at = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
    pipeline = VisualSignalRecordingPipeline(
        analysis_pipeline=analysis_pipeline,
        recorder=SignalRecorder(SignalHistory()),
        observation_recorder=observation_recorder,
    )

    pipeline.analyze_and_record(
        image=np.zeros((100, 100, 3), dtype=np.uint8),
        created_at=created_at,
    )

    assert observation_recorder.resolve_calls[0][
        "exit_visual_price_context"
    ] is context


class FakeSignalRecordWriter:
    def __init__(self) -> None:
        self.records: list[SignalRecord] = []

    def write(
        self,
        record: SignalRecord,
    ) -> None:
        self.records.append(record)


def test_analyze_and_record_adds_visual_signal_to_history() -> None:

    history = SignalHistory()

    pipeline = VisualSignalRecordingPipeline(
        analysis_pipeline=FakeVisualStrategySignalAnalysisPipeline(),
        recorder=SignalRecorder(history),
    )

    created_at = datetime(
        2026,
        1,
        1,
        tzinfo=UTC,
    )

    record = pipeline.analyze_and_record(
        image=np.zeros(
            (100, 100, 3),
            dtype=np.uint8,
        ),
        created_at=created_at,
    )

    assert history.latest() is record
    assert record.signal.direction is SignalDirection.CALL
    assert record.signal.strength is SignalStrength.HIGH
    assert record.signal.reason == "Visual strategy conditions confirmed."
    assert record.created_at is created_at
    assert record.source == "visual_strategy_signal_analysis"


def test_analyze_and_record_writes_visual_signal_when_writer_is_configured() -> None:

    history = SignalHistory()
    writer = FakeSignalRecordWriter()

    pipeline = VisualSignalRecordingPipeline(
        analysis_pipeline=FakeVisualStrategySignalAnalysisPipeline(),
        recorder=SignalRecorder(history),
        record_writer=writer,
    )

    record = pipeline.analyze_and_record(
        image=np.zeros(
            (100, 100, 3),
            dtype=np.uint8,
        ),
    )

    assert history.latest() is record
    assert writer.records == [
        record,
    ]


def test_pipeline_suppresses_second_actionable_signal_in_same_candle() -> None:

    history = SignalHistory()
    writer = FakeSignalRecordWriter()

    pipeline = VisualSignalRecordingPipeline(
        analysis_pipeline=(FakeVisualStrategySignalAnalysisPipeline()),
        recorder=SignalRecorder(
            history,
        ),
        record_writer=writer,
    )

    first = pipeline.analyze_and_record(
        image=np.zeros(
            (100, 100, 3),
            dtype=np.uint8,
        ),
        created_at=datetime(
            2026,
            7,
            31,
            10,
            30,
            5,
            tzinfo=UTC,
        ),
    )

    duplicate = pipeline.analyze_and_record(
        image=np.zeros(
            (100, 100, 3),
            dtype=np.uint8,
        ),
        created_at=datetime(
            2026,
            7,
            31,
            10,
            30,
            20,
            tzinfo=UTC,
        ),
    )

    assert first.disposition is SignalRecordDisposition.ACTIONABLE_ACCEPTED
    assert first.is_actionable is True

    assert duplicate.disposition is SignalRecordDisposition.DUPLICATE_SUPPRESSED
    assert duplicate.signal.direction is SignalDirection.CALL
    assert duplicate.is_actionable is False

    assert writer.records == [
        first,
        duplicate,
    ]


def test_pipeline_accepts_same_direction_in_next_candle() -> None:

    pipeline = VisualSignalRecordingPipeline(
        analysis_pipeline=(FakeVisualStrategySignalAnalysisPipeline()),
        recorder=SignalRecorder(
            SignalHistory(),
        ),
    )

    first = pipeline.analyze_and_record(
        image=np.zeros(
            (100, 100, 3),
            dtype=np.uint8,
        ),
        created_at=datetime(
            2026,
            7,
            31,
            10,
            30,
            20,
            tzinfo=UTC,
        ),
    )

    second = pipeline.analyze_and_record(
        image=np.zeros(
            (100, 100, 3),
            dtype=np.uint8,
        ),
        created_at=datetime(
            2026,
            7,
            31,
            10,
            30,
            35,
            tzinfo=UTC,
        ),
    )

    assert first.is_actionable is True
    assert second.is_actionable is True
