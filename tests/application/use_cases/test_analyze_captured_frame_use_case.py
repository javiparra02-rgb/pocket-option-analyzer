from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np

from pocket_option_analyzer.application.use_cases import (
    AnalyzeCapturedFrameUseCase,
)
from pocket_option_analyzer.domain.signals import (
    MarketSignal,
    SignalDirection,
    SignalRecord,
    SignalStrength,
)
from pocket_option_analyzer.vision.models import ChartRegion


@dataclass(frozen=True, slots=True)
class FakeFrame:
    image: np.ndarray

    captured_at: datetime


@dataclass(frozen=True, slots=True)
class FakeFrameWithoutTimestamp:
    image: np.ndarray


@dataclass(frozen=True, slots=True)
class FakeFrameWithPriceObservationImage:
    image: np.ndarray
    price_observation_image: np.ndarray


@dataclass(frozen=True, slots=True)
class FakeFrameWithCaptureGeometry:
    image: np.ndarray
    chart_region: ChartRegion
    price_observation_region: ChartRegion


@dataclass(frozen=True, slots=True)
class FakeFrameWithId:
    frame_id: int
    image: np.ndarray


@dataclass(frozen=True, slots=True)
class FakeFrameWithIdentityMetadata:
    frame_id: int
    timestamp: datetime
    monotonic_timestamp_ns: int
    source_key: str
    image: np.ndarray


class FakeVisualSignalRecordingPipeline:
    def __init__(self) -> None:
        self.received_image = None
        self.received_created_at = None
        self.received_source = None
        self.received_price_observation_image = None
        self.received_chart_region = None
        self.received_price_observation_region = None
        self.received_frame_id = None
        self.received_monotonic_timestamp = None
        self.received_source_key = None
        self.received_session_key = None
        self.started_sessions: list[str] = []
        self.stop_calls = 0

    def start_session(self, *, session_key: str) -> None:
        self.started_sessions.append(session_key)

    def stop_session(self) -> None:
        self.stop_calls += 1

    def analyze_and_record(
        self,
        image,
        created_at=None,
        source="visual_strategy_signal_analysis",
        price_observation_image=None,
        chart_region=None,
        price_observation_region=None,
        frame_id=None,
        monotonic_timestamp=None,
        source_key=None,
        session_key=None,
    ) -> SignalRecord:
        self.received_image = image
        self.received_created_at = created_at
        self.received_source = source
        self.received_price_observation_image = price_observation_image
        self.received_chart_region = chart_region
        self.received_price_observation_region = price_observation_region
        self.received_frame_id = frame_id
        self.received_monotonic_timestamp = monotonic_timestamp
        self.received_source_key = source_key
        self.received_session_key = session_key

        return SignalRecord(
            signal=MarketSignal(
                direction=SignalDirection.CALL,
                strength=SignalStrength.HIGH,
                reason="Visual strategy conditions confirmed.",
            ),
            created_at=created_at
            or datetime(
                2026,
                1,
                1,
                tzinfo=UTC,
            ),
            source=source,
        )


def test_execute_analyzes_frame_image_and_preserves_capture_datetime() -> None:

    image = np.zeros(
        (100, 100, 3),
        dtype=np.uint8,
    )
    captured_at = datetime(
        2026,
        1,
        1,
        tzinfo=UTC,
    )

    frame = FakeFrame(
        image=image,
        captured_at=captured_at,
    )

    pipeline = FakeVisualSignalRecordingPipeline()

    use_case = AnalyzeCapturedFrameUseCase(
        pipeline=pipeline,
    )

    record = use_case.execute(
        frame=frame,
    )

    assert record.signal.direction is SignalDirection.CALL
    assert record.signal.strength is SignalStrength.HIGH
    assert record.created_at is captured_at
    assert record.source == "captured_frame_visual_analysis"
    assert pipeline.received_image is image
    assert pipeline.received_created_at is captured_at
    assert pipeline.received_source == "captured_frame_visual_analysis"


def test_execute_accepts_frame_without_timestamp() -> None:

    image = np.zeros(
        (100, 100, 3),
        dtype=np.uint8,
    )

    frame = FakeFrameWithoutTimestamp(
        image=image,
    )

    pipeline = FakeVisualSignalRecordingPipeline()

    use_case = AnalyzeCapturedFrameUseCase(
        pipeline=pipeline,
    )

    record = use_case.execute(
        frame=frame,
    )

    assert record.signal.direction is SignalDirection.CALL
    assert pipeline.received_image is image
    assert pipeline.received_created_at is None
    assert pipeline.received_price_observation_image is None
    assert record.source == "captured_frame_visual_analysis"


def test_execute_propagates_price_observation_image_by_identity() -> None:
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    price_observation_image = np.zeros((20, 100, 3), dtype=np.uint8)
    pipeline = FakeVisualSignalRecordingPipeline()
    use_case = AnalyzeCapturedFrameUseCase(pipeline=pipeline)

    use_case.execute(
        frame=FakeFrameWithPriceObservationImage(
            image=image,
            price_observation_image=price_observation_image,
        )
    )

    assert pipeline.received_image is image
    assert pipeline.received_price_observation_image is price_observation_image


def test_execute_propagates_capture_geometry_by_identity() -> None:
    chart_region = ChartRegion(x=10, y=20, width=100, height=80)
    price_region = ChartRegion(x=30, y=40, width=100, height=80)
    pipeline = FakeVisualSignalRecordingPipeline()

    AnalyzeCapturedFrameUseCase(pipeline=pipeline).execute(
        frame=FakeFrameWithCaptureGeometry(
            image=np.zeros((80, 100, 3), dtype=np.uint8),
            chart_region=chart_region,
            price_observation_region=price_region,
        )
    )

    assert pipeline.received_chart_region is chart_region
    assert pipeline.received_price_observation_region is price_region


def test_execute_propagates_existing_frame_id() -> None:
    pipeline = FakeVisualSignalRecordingPipeline()

    AnalyzeCapturedFrameUseCase(pipeline=pipeline).execute(
        frame=FakeFrameWithId(
            frame_id=42,
            image=np.zeros((80, 100, 3), dtype=np.uint8),
        )
    )

    assert pipeline.received_frame_id == 42


def test_execute_propagates_real_identity_metadata_for_active_session() -> None:
    pipeline = FakeVisualSignalRecordingPipeline()
    use_case = AnalyzeCapturedFrameUseCase(pipeline=pipeline)
    captured_at = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)

    use_case.start_session(session_key="session-01")
    use_case.execute(
        frame=FakeFrameWithIdentityMetadata(
            frame_id=42,
            timestamp=captured_at,
            monotonic_timestamp_ns=12_345_678_900,
            source_key="win32_hwnd:1234",
            image=np.zeros((80, 100, 3), dtype=np.uint8),
        )
    )
    use_case.stop_session()

    assert pipeline.started_sessions == ["session-01"]
    assert pipeline.received_created_at is captured_at
    assert pipeline.received_frame_id == 42
    assert pipeline.received_monotonic_timestamp == 12.3456789
    assert pipeline.received_source_key == "win32_hwnd:1234"
    assert pipeline.received_session_key == "session-01"
    assert pipeline.stop_calls == 1
