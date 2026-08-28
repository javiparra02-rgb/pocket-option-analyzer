from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np
import pytest

from pocket_option_analyzer.application.evidence import (
    IdentityShadowEvidenceConfig,
)
from pocket_option_analyzer.application.market import (
    CurrentCandleIdentityConfig,
    CurrentCandleIdentityResolver,
    CurrentCandleIdentityRuntimeShadow,
    CurrentCandleIdentityStatus,
)
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
from pocket_option_analyzer.infrastructure.capture.models import Frame
from pocket_option_analyzer.infrastructure.evidence import (
    FilesystemVisualEvidenceRecorder,
)
from pocket_option_analyzer.vision.services import (
    CandleSeriesMembershipResolver,
    PocketOptionCurrentVisualPriceExtractor,
    PocketOptionCurrentVisualPriceSearchWindowResolver,
    PocketOptionExpiryOverlayEvidenceResolver,
)


@dataclass(frozen=True, slots=True)
class FakeFrame:
    image: np.ndarray

    captured_at: datetime


class FakeCaptureService:
    def __init__(
        self,
        frames,
    ) -> None:
        self._frames = list(frames)

    def capture_once(
        self,
    ):
        if not self._frames:
            return None

        return self._frames.pop(0)


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
            (100, 1161, 3),
            dtype=np.uint8,
        ),
        captured_at=datetime(
            2026,
            1,
            1,
            tzinfo=UTC,
        ),
    )


def test_factory_creates_pipeline_that_records_in_memory() -> None:

    history = SignalHistory()

    pipeline = SignalPipelineFactory.create_signal_recording_pipeline(
        signal_history=history,
    )

    record = pipeline.analyze_and_record(
        image=np.zeros(
            (100, 1161, 3),
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
            (100, 1161, 3),
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
            (100, 1161, 3),
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
            (100, 1161, 3),
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


def test_factory_creates_frame_analysis_loop_service() -> None:

    history = SignalHistory()
    frame = _frame()

    loop_service = SignalPipelineFactory.create_frame_analysis_loop_service(
        capture_service=FakeCaptureService(
            frames=[
                frame,
            ],
        ),
        signal_history=history,
        interval_seconds=0.0,
    )

    record = loop_service.run_once()

    assert record is not None
    assert history.latest() is record
    assert record.signal.direction is SignalDirection.NONE
    assert record.created_at is frame.captured_at
    assert record.source == "captured_frame_visual_analysis"


def test_factory_creates_frame_analysis_loop_service_that_writes_jsonl_file(
    tmp_path,
) -> None:

    history = SignalHistory()
    frame = _frame()
    file_path = tmp_path / "signals" / "loop_signals.jsonl"

    loop_service = SignalPipelineFactory.create_frame_analysis_loop_service(
        capture_service=FakeCaptureService(
            frames=[
                frame,
            ],
        ),
        signal_history=history,
        signal_file_path=file_path,
        interval_seconds=0.0,
    )

    record = loop_service.run_once()

    assert record is not None
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


def test_factory_creates_analysis_runtime_service() -> None:

    history = SignalHistory()
    frame = _frame()

    runtime_service = SignalPipelineFactory.create_analysis_runtime_service(
        capture_service=FakeCaptureService(
            frames=[
                frame,
            ],
        ),
        signal_history=history,
        interval_seconds=0.0,
    )

    record = runtime_service.run_once()

    assert record is not None
    assert history.latest() is record
    assert record.signal.direction is SignalDirection.NONE
    assert record.created_at is frame.captured_at
    assert record.source == "captured_frame_visual_analysis"
    assert runtime_service.is_running is False


def test_factory_creates_analysis_runtime_service_that_writes_jsonl_file(
    tmp_path,
) -> None:

    history = SignalHistory()
    frame = _frame()
    file_path = tmp_path / "signals" / "runtime_signals.jsonl"

    runtime_service = SignalPipelineFactory.create_analysis_runtime_service(
        capture_service=FakeCaptureService(
            frames=[
                frame,
            ],
        ),
        signal_history=history,
        signal_file_path=file_path,
        interval_seconds=0.0,
    )

    record = runtime_service.run_once()

    assert record is not None
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


def test_factory_injects_current_visual_price_extractor() -> None:
    pipeline = SignalPipelineFactory._create_market_analysis_pipeline()

    assert isinstance(
        pipeline._current_visual_price_extractor,
        PocketOptionCurrentVisualPriceExtractor,
    )
    assert pipeline._current_visual_price_extractor._effective_chart_right_x is None
    assert isinstance(
        pipeline._current_visual_price_extractor._search_window_resolver,
        PocketOptionCurrentVisualPriceSearchWindowResolver,
    )


def test_factory_injects_candle_series_membership_resolver() -> None:
    pipeline = SignalPipelineFactory._create_market_analysis_pipeline()

    assert isinstance(
        pipeline._membership_resolver,
        CandleSeriesMembershipResolver,
    )


def test_factory_injects_expiry_overlay_evidence_resolver() -> None:
    pipeline = SignalPipelineFactory._create_market_analysis_pipeline()

    assert isinstance(
        pipeline._overlay_evidence_resolver,
        PocketOptionExpiryOverlayEvidenceResolver,
    )


def test_factory_injects_one_always_on_in_memory_identity_shadow() -> None:
    pipeline = SignalPipelineFactory.create_visual_signal_recording_pipeline()
    second_pipeline = (
        SignalPipelineFactory.create_visual_signal_recording_pipeline()
    )
    analysis_pipeline = pipeline._analysis_pipeline
    shadow = analysis_pipeline.current_candle_identity_shadow
    second_shadow = (
        second_pipeline._analysis_pipeline.current_candle_identity_shadow
    )

    assert isinstance(shadow, CurrentCandleIdentityRuntimeShadow)
    assert isinstance(shadow.resolver, CurrentCandleIdentityResolver)
    assert shadow.resolver.config == CurrentCandleIdentityConfig()
    assert shadow.last_resolution is None
    assert second_shadow is not shadow
    assert second_shadow.resolver is not shadow.resolver
    assert pipeline._visual_evidence_recorder is None


def test_factory_runtime_executes_identity_shadow_with_real_frame_metadata() -> None:
    captured_at = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)
    frame = Frame(
        frame_id=17,
        timestamp=captured_at,
        monotonic_timestamp_ns=123_500_000_000,
        source_key="win32_hwnd:321",
        image=np.zeros((100, 1161, 3), dtype=np.uint8),
    )
    runtime = SignalPipelineFactory.create_analysis_runtime_service(
        capture_service=FakeCaptureService(frames=[frame]),
    )

    runtime.run_once()

    analysis_pipeline = (
        runtime._loop_service._analysis_use_case._pipeline._analysis_pipeline
    )
    resolution = analysis_pipeline.last_current_candle_identity_resolution
    assert resolution is not None
    assert resolution.result.status is CurrentCandleIdentityStatus.UNAVAILABLE
    assert resolution.trace.frame_id == 17
    assert resolution.trace.wall_timestamp is captured_at
    assert resolution.trace.monotonic_timestamp == 123.5
    assert resolution.trace.source_key == "win32_hwnd:321"


def test_visual_evidence_adapter_is_disabled_without_directory(tmp_path) -> None:
    unused_directory = tmp_path / "must-not-exist"
    pipeline = SignalPipelineFactory.create_visual_signal_recording_pipeline()

    assert pipeline._visual_evidence_recorder is None
    assert unused_directory.exists() is False


def test_visual_evidence_adapter_is_enabled_only_with_directory(tmp_path) -> None:
    evidence_directory = tmp_path / "evidence"

    pipeline = SignalPipelineFactory.create_visual_signal_recording_pipeline(
        observation_file_path=tmp_path / "strategy_observations.jsonl",
        visual_evidence_directory=evidence_directory,
        application_version="0.1.0-test",
    )

    recorder = pipeline._visual_evidence_recorder
    assert isinstance(recorder, FilesystemVisualEvidenceRecorder)
    assert recorder.directory == evidence_directory
    assert (evidence_directory / "session_metadata.json").is_file()
    assert pipeline._identity_evidence_recorder is None


def test_identity_evidence_uses_same_opt_in_filesystem_adapter(tmp_path) -> None:
    evidence_directory = tmp_path / "evidence"
    config = IdentityShadowEvidenceConfig()

    pipeline = SignalPipelineFactory.create_visual_signal_recording_pipeline(
        visual_evidence_directory=evidence_directory,
        identity_evidence_config=config,
    )

    assert pipeline._identity_evidence_recorder is pipeline._visual_evidence_recorder
    assert pipeline._visual_evidence_recorder._identity_config is config


def test_identity_config_without_visual_root_is_not_silently_persisted() -> None:
    with pytest.raises(ValueError, match="visual_evidence_directory"):
        SignalPipelineFactory.create_visual_signal_recording_pipeline(
            identity_evidence_config=IdentityShadowEvidenceConfig(),
        )
