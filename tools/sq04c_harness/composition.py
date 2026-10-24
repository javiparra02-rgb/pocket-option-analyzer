"""Synthetic source plus unchanged public product dependencies; no live backend."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from .config import HarnessConfig
from .isolation import inventory
from .metrics import Metrics
from .reconcile import Census, Reconciliation, reconcile
from .supervisor import Supervisor


@dataclass(frozen=True)
class SyntheticFrame:
    image: Any
    frame_id: int
    created_at: datetime
    monotonic_timestamp_ns: int
    source_key: str = "SYNTHETIC_NO_SCREEN"
    instrument_context_image: Any = None


class SyntheticSource:
    """Generates pixels internally; accepts neither file paths nor capture callbacks."""

    def __init__(self, *, frames: tuple[SyntheticFrame, ...] | None = None) -> None:
        if frames is not None:
            import numpy as np

            if type(frames) is not tuple or not frames:
                raise ValueError("Synthetic sequence must be a nonempty tuple")
            for index, frame in enumerate(frames):
                if type(frame) is not SyntheticFrame:
                    raise ValueError("Only synthetic frame data is admitted")
                if frame.source_key != "SYNTHETIC_NO_SCREEN":
                    raise ValueError("Synthetic source identity required")
                if type(frame.frame_id) is not int or frame.frame_id <= 0:
                    raise ValueError("Positive synthetic frame ID required")
                if (
                    type(frame.monotonic_timestamp_ns) is not int
                    or frame.monotonic_timestamp_ns < 0
                    or frame.created_at.utcoffset() is None
                ):
                    raise ValueError("Explicit synthetic timestamps required")
                for role, pixels in enumerate(
                    (frame.image, frame.instrument_context_image)
                ):
                    if role == 1 and pixels is None:
                        continue
                    if (
                        type(pixels) is not np.ndarray
                        or pixels.dtype != np.uint8
                        or pixels.ndim != 3
                        or pixels.shape[2] != 3
                        or not pixels.size
                    ):
                        raise ValueError("Synthetic input must be uint8 BGR pixels")
                if index and (
                    frame.frame_id <= frames[index - 1].frame_id
                    or frame.created_at <= frames[index - 1].created_at
                    or frame.monotonic_timestamp_ns
                    <= frames[index - 1].monotonic_timestamp_ns
                ):
                    raise ValueError("Synthetic sequence must increase in order")
        self.frames = frames
        self.count = 0

    def capture_once(self) -> SyntheticFrame:
        import numpy as np

        self.count += 1
        if self.frames is not None:
            if self.count > len(self.frames):
                raise RuntimeError("Synthetic input exhausted; no frame replay")
            return self.frames[self.count - 1]
        return SyntheticFrame(
            np.zeros((64, 64, 3), dtype=np.uint8),
            self.count,
            datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=self.count),
            self.count * 1_000_000_000,
        )


class ObservedAnalysis:
    """Calls the use case exactly once, observing its public results afterward."""

    def __init__(self, analysis: Any, pipeline: Any, census: Census) -> None:
        self.analysis, self.pipeline, self.census = analysis, pipeline, census
        self.session_key: str | None = None

    def start_session(self, *, session_key: str) -> None:
        self.analysis.start_session(session_key=session_key)
        self.session_key = session_key

    def stop_session(self) -> None:
        self.analysis.stop_session()

    def execute(self, frame: SyntheticFrame) -> Any:
        try:
            result = self.analysis.execute(frame)
            self.census.observed_frames.append(
                {
                    "frame_id": frame.frame_id,
                    "observed_at": frame.created_at.isoformat(),
                    "source": "sq04c_synthetic",
                    "source_key": frame.source_key,
                    "session_key": self.session_key,
                }
            )
            return result
        finally:
            accepted = self.pipeline.accepted_evidence.last_accepted
            if accepted is not None:
                self.census.acceptance(accepted.to_dict())
            selected = self.pipeline.accepted_evidence.last_exit
            if selected is not None:
                self.census.evaluation(selected.to_dict()["exit_evaluation"])


def build_synthetic(
    config: HarnessConfig, *, frames: tuple[SyntheticFrame, ...] | None = None
) -> Supervisor:
    evidence_config = config.validate()
    source = SyntheticSource(frames=frames)
    if frames is not None and len(frames) != config.max_cycles:
        raise ValueError("One supplied synthetic frame per configured cycle required")
    for path in (config.evidence, config.sq03, config.supervision):
        if path.exists():
            raise ValueError("Each synthetic session requires fresh output directories")

    from pocket_option_analyzer.application.runtime import AnalysisRuntimeService
    from pocket_option_analyzer.application.use_cases import (
        AnalyzeCapturedFrameUseCase,
        FrameAnalysisLoopService,
    )
    from pocket_option_analyzer.infrastructure.bootstrap import SignalPipelineFactory
    from pocket_option_analyzer.infrastructure.evidence.observational_evidence_writer import (  # noqa: E501
        ObservationalEvidenceWriter,
    )
    from pocket_option_analyzer.vision.models import CandleColorProfile

    config.sq03.mkdir(parents=True, exist_ok=False)
    config.supervision.mkdir(parents=True, exist_ok=False)
    census = Census()
    pipeline = SignalPipelineFactory.create_visual_signal_recording_pipeline(
        signal_file_path=config.sq03 / "signals.jsonl",
        observation_file_path=config.sq03 / "observations.jsonl",
        color_profile=CandleColorProfile.white_red(),
        observational_evidence_config=(
            evidence_config if config.pipeline_observational else None
        ),
    )
    recorder = pipeline.observational_evidence
    writer = recorder.writer if recorder is not None else None
    if writer is not None and not isinstance(writer, ObservationalEvidenceWriter):
        raise TypeError("Public writer lacks the verified lifecycle contract")
    analysis = AnalyzeCapturedFrameUseCase(pipeline=pipeline, source="sq04c_synthetic")
    observed = ObservedAnalysis(analysis, pipeline, census)
    loop = FrameAnalysisLoopService(
        capture_service=source,
        analysis_use_case=observed,
        interval_seconds=config.interval_seconds,
    )
    runtime = AnalysisRuntimeService(loop)

    def reconcile_session() -> Reconciliation:
        if writer is not None:
            return reconcile(writer, census, config.sq03)
        from .reconcile import sq03_records

        accepted, _ = sq03_records(config.sq03)
        issues = list(census.conflicts)
        if accepted != census.acceptances:
            issues.append("SQ03 OFF census mismatch")
        if inventory(config.evidence):
            issues.append("OFF wrote observational evidence")
        return Reconciliation(
            not issues, {}, issues, [], {}, 0, "SYNTHETIC_OFF_NO_ORIGINALS_REQUESTED"
        )

    return Supervisor(
        pipeline=pipeline,
        recorder=recorder,
        writer=writer,
        analysis=observed,
        loop=loop,
        runtime=runtime,
        reconcile=reconcile_session,
        metrics=Metrics(config.sample_capacity),
        interval=config.interval_seconds,
        max_cycles=config.max_cycles,
        known_acceptances=lambda: set(census.acceptances),
    )
