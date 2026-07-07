from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np

from pocket_option_analyzer.domain.indicators import (
    EmaSnapshot,
    IndicatorSnapshot,
    RsiSnapshot,
    StochasticSnapshot,
)
from pocket_option_analyzer.domain.signals import (
    SignalDirection,
    SignalHistory,
)
from pocket_option_analyzer.infrastructure.bootstrap import (
    SignalPipelineFactory,
)


@dataclass(frozen=True, slots=True)
class FakeFrame:

    image: np.ndarray

    captured_at: datetime


def _indicators() -> IndicatorSnapshot:

    return IndicatorSnapshot(
        ema=EmaSnapshot(
            fast_value=105.0,
            slow_value=100.0,
            separation_candles=3,
        ),
        rsi=RsiSnapshot(
            value=57.0,
        ),
        stochastic=StochasticSnapshot(
            k_previous=18.0,
            d_previous=20.0,
            k_value=24.0,
            d_value=21.0,
        ),
    )


def _frame() -> FakeFrame:

    return FakeFrame(
        image=np.zeros(
            (100, 100, 3),
            dtype=np.uint8,
        ),
        captured_at=datetime(
            2026,
            1,
            1,
            tzinfo=timezone.utc,
        ),
    )


def test_factory_creates_pipeline_that_records_in_memory() -> None:

    history = SignalHistory()

    pipeline = SignalPipelineFactory.create_signal_recording_pipeline(
        signal_history=history,
    )

    record = pipeline.analyze_and_record(
        image=np.zeros(
            (100, 100, 3),
            dtype=np.uint8,
        ),
        indicators=_indicators(),
    )

    assert history.latest() is record
    assert record.signal.direction is SignalDirection.NONE


def test_factory_creates_pipeline_that_writes_jsonl_file(
    tmp_path,
) -> None:

    history = SignalHistory()
    file_path = tmp_path / "signals" / "signals.jsonl"

    pipeline = SignalPipelineFactory.create_signal_recording_pipeline(
        signal_history=history,
        signal_file_path=file_path,
    )

    record = pipeline.analyze_and_record(
        image=np.zeros(
            (100, 100, 3),
            dtype=np.uint8,
        ),
        indicators=_indicators(),
    )

    assert history.latest() is record
    assert file_path.exists()

    lines = file_path.read_text(
        encoding="utf-8",
    ).splitlines()

    assert len(lines) == 1

    data = json.loads(lines[0])

    assert data["direction"] == "none"
    assert data["strength"] == "none"
    assert data["is_actionable"] is False


def test_factory_creates_visual_pipeline_that_records_in_memory() -> None:

    history = SignalHistory()

    pipeline = SignalPipelineFactory.create_visual_signal_recording_pipeline(
        signal_history=history,
    )

    record = pipeline.analyze_and_record(
        image=np.zeros(
            (100, 100, 3),
            dtype=np.uint8,
        ),
    )

    assert history.latest() is record
    assert record.signal.direction is SignalDirection.NONE
    assert record.source == "visual_strategy_signal_analysis"


def test_factory_creates_visual_pipeline_that_writes_jsonl_file(
    tmp_path,
) -> None:

    history = SignalHistory()
    file_path = tmp_path / "signals" / "visual_signals.jsonl"

    pipeline = SignalPipelineFactory.create_visual_signal_recording_pipeline(
        signal_history=history,
        signal_file_path=file_path,
    )

    record = pipeline.analyze_and_record(
        image=np.zeros(
            (100, 100, 3),
            dtype=np.uint8,
        ),
    )

    assert history.latest() is record
    assert file_path.exists()

    lines = file_path.read_text(
        encoding="utf-8",
    ).splitlines()

    assert len(lines) == 1

    data = json.loads(lines[0])

    assert data["direction"] == "none"
    assert data["strength"] == "none"
    assert data["source"] == "visual_strategy_signal_analysis"
    assert data["is_actionable"] is False


def test_factory_creates_captured_frame_analysis_use_case() -> None:

    history = SignalHistory()

    use_case = SignalPipelineFactory.create_captured_frame_analysis_use_case(
        signal_history=history,
    )

    frame = _frame()

    record = use_case.execute(
        frame=frame,
    )

    assert history.latest() is record
    assert record.signal.direction is SignalDirection.NONE
    assert record.created_at is frame.captured_at
    assert record.source == "captured_frame_visual_analysis"


def test_factory_creates_captured_frame_use_case_that_writes_jsonl_file(
    tmp_path,
) -> None:

    history = SignalHistory()
    file_path = tmp_path / "signals" / "captured_frame_signals.jsonl"

    use_case = SignalPipelineFactory.create_captured_frame_analysis_use_case(
        signal_history=history,
        signal_file_path=file_path,
    )

    record = use_case.execute(
        frame=_frame(),
    )

    assert history.latest() is record
    assert file_path.exists()

    lines = file_path.read_text(
        encoding="utf-8",
    ).splitlines()

    assert len(lines) == 1

    data = json.loads(lines[0])

    assert data["direction"] == "none"
    assert data["strength"] == "none"
    assert data["source"] == "captured_frame_visual_analysis"
    assert data["is_actionable"] is False