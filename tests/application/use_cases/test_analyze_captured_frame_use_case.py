from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

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


@dataclass(frozen=True, slots=True)
class FakeFrame:

    image: np.ndarray

    captured_at: datetime


@dataclass(frozen=True, slots=True)
class FakeFrameWithoutTimestamp:

    image: np.ndarray


class FakeVisualSignalRecordingPipeline:

    def __init__(self) -> None:
        self.received_image = None
        self.received_created_at = None
        self.received_source = None

    def analyze_and_record(
        self,
        image,
        created_at=None,
        source="visual_strategy_signal_analysis",
    ) -> SignalRecord:
        self.received_image = image
        self.received_created_at = created_at
        self.received_source = source

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
                tzinfo=timezone.utc,
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
        tzinfo=timezone.utc,
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
    assert record.source == "captured_frame_visual_analysis"