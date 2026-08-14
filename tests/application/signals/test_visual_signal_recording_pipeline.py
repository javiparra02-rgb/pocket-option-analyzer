from datetime import UTC, datetime

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

    def analyze(
        self,
        image,
        price_observation_image=None,
        chart_region=None,
        price_observation_region=None,
    ) -> MarketSignal:
        self.received_image = image
        self.received_price_observation_image = price_observation_image
        self.received_chart_region = chart_region
        self.received_price_observation_region = price_observation_region
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
