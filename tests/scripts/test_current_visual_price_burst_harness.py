from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import cv2
import numpy as np
import pytest

import scripts.current_visual_price_burst_harness as harness_module
from pocket_option_analyzer.infrastructure.capture.models import Frame
from pocket_option_analyzer.vision.models import (
    ChartRegion,
    CurrentVisualPriceAnalysis,
    CurrentVisualPriceDetectionTrace,
    CurrentVisualPriceExtraction,
    CurrentVisualPriceRejectionCounts,
    CurrentVisualPriceStatus,
)
from pocket_option_analyzer.vision.services import (
    PocketOptionCurrentVisualPriceExtractor,
    PocketOptionCurrentVisualPriceSearchWindowResolver,
)
from scripts.current_visual_price_burst_harness import (
    BurstTechnicalStatus,
    CalibrationHarnessError,
    CurrentVisualPriceBurstHarness,
    GitProvenance,
    HarnessConfig,
    TechnicalFailureReason,
    build_productive_extractor,
    replay_current_visual_price_frame,
    validate_external_output_directory,
)

COMMIT = "8f5e68afa92d54686662e324b17136e30997a708"


class FakeClock:
    def __init__(self, current_ns: int = 1_000_000_000) -> None:
        self.current_ns = current_ns
        self.sleep_calls: list[float] = []

    def monotonic_ns(self) -> int:
        return self.current_ns

    def sleep(self, seconds: float) -> None:
        self.sleep_calls.append(seconds)
        self.current_ns += round(seconds * 1_000_000_000)

    def advance(self, nanoseconds: int) -> None:
        self.current_ns += nanoseconds


class FakeCaptureService:
    def __init__(
        self,
        items: list[Frame | None | BaseException],
        *,
        clock: FakeClock,
        duration_ns: int = 20_000_000,
    ) -> None:
        self._items = items
        self._clock = clock
        self._duration_ns = duration_ns
        self.call_count = 0

    def capture_once(self) -> Frame | None:
        item = self._items[self.call_count]
        self.call_count += 1
        self._clock.advance(self._duration_ns)
        if isinstance(item, BaseException):
            raise item
        return item


class FakeExtractor:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.images: list[np.ndarray] = []
        self._error = error

    def extract_with_trace(self, image: np.ndarray) -> CurrentVisualPriceAnalysis:
        self.images.append(image)
        if self._error is not None:
            raise self._error
        height, width = image.shape[:2]
        extraction = CurrentVisualPriceExtraction(
            price=None,
            status=CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE,
            diagnostic="fake_no_candidate",
        )
        trace = CurrentVisualPriceDetectionTrace(
            status=extraction.status,
            image_width=int(width),
            image_height=int(height),
            effective_chart_right_x=int(width),
            effective_chart_right_source="fake",
            band_start=0,
            band_end=int(width),
            band_width=int(width),
            safe_top=0,
            safe_bottom=0,
            masked_pixel_count=0,
            candidates=(),
            rejection_counts=CurrentVisualPriceRejectionCounts(
                rows_without_mask_pixels=int(height)
            ),
            decision_diagnostic="fake_no_candidate",
        )
        return CurrentVisualPriceAnalysis(extraction=extraction, trace=trace)


@dataclass
class FakeGitProvider:
    head: str = COMMIT
    dirty: bool = False
    branch: str = "feat/visual-price-resolution"

    def resolve(self, repository_root: Path, remote: str) -> GitProvenance:
        return GitProvenance(
            branch=self.branch,
            head=self.head,
            dirty=self.dirty,
            ahead=0,
            behind=0,
            remote=remote,
        )


def make_frame(
    frame_id: int,
    *,
    chart: np.ndarray | None = None,
    price: np.ndarray | None = None,
    source: str | None = "win32_hwnd:123",
    chart_region: ChartRegion | None = None,
    price_region: ChartRegion | None = None,
    monotonic_ns: int | None = None,
) -> Frame:
    resolved_chart = (
        chart
        if chart is not None
        else np.full((6, 8, 4), frame_id % 255, dtype=np.uint8)
    )
    resolved_price = (
        price
        if price is not None
        else np.full((6, 8, 4), (frame_id + 20) % 255, dtype=np.uint8)
    )
    resolved_chart_region = chart_region or ChartRegion(x=0, y=10, width=8, height=6)
    resolved_price_region = price_region or ChartRegion(x=0, y=10, width=8, height=6)
    return Frame(
        frame_id=frame_id,
        timestamp=datetime(2026, 8, 31, tzinfo=UTC)
        + timedelta(microseconds=frame_id),
        image=resolved_chart,
        price_observation_image=resolved_price,
        chart_region=resolved_chart_region,
        price_observation_region=resolved_price_region,
        monotonic_timestamp_ns=(
            monotonic_ns if monotonic_ns is not None else frame_id * 100
        ),
        source_key=source,
    )


def make_frames(count: int, *, start: int = 1) -> list[Frame]:
    return [make_frame(frame_id) for frame_id in range(start, start + count)]


def jsonl(path: Path) -> list[dict[str, object]]:
    return [
        cast(dict[str, object], json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def build_harness(
    *,
    capture: FakeCaptureService,
    clock: FakeClock,
    extractor: FakeExtractor | PocketOptionCurrentVisualPriceExtractor | None = None,
    git: FakeGitProvider | None = None,
    png_encoder=None,
) -> CurrentVisualPriceBurstHarness:
    return CurrentVisualPriceBurstHarness(
        capture_service=capture,
        extractor=extractor or FakeExtractor(),
        git_provider=git or FakeGitProvider(),
        monotonic_clock_ns=clock.monotonic_ns,
        wall_clock=lambda: datetime(2026, 8, 31, tzinfo=UTC),
        sleeper=clock.sleep,
        png_encoder=png_encoder,
        session_id_factory=lambda: "test_session",
    )


def run_one_burst(
    tmp_path: Path,
    *,
    frames: list[Frame | None | BaseException] | None = None,
    capture_duration_ns: int = 20_000_000,
    extractor: FakeExtractor | PocketOptionCurrentVisualPriceExtractor | None = None,
    git: FakeGitProvider | None = None,
    png_encoder=None,
    inter_burst_delay: float = 0.0,
    candidate_bursts: int = 1,
) -> tuple[Path, CurrentVisualPriceBurstHarness, FakeCaptureService, FakeClock]:
    clock = FakeClock()
    all_frames = frames or make_frames(5 + 5 * candidate_bursts)
    capture = FakeCaptureService(
        all_frames,
        clock=clock,
        duration_ns=capture_duration_ns,
    )
    harness = build_harness(
        capture=capture,
        clock=clock,
        extractor=extractor,
        git=git,
        png_encoder=png_encoder,
    )
    repository = tmp_path / "repository"
    repository.mkdir()
    output = tmp_path / "evidence"
    harness.run(
        config=HarnessConfig(
            frames_per_burst=5,
            target_fps=8.0,
            candidate_bursts=candidate_bursts,
            preflight_frames=5,
            inter_burst_delay_seconds=inter_burst_delay,
        ),
        output_directory=output,
        repository_root=repository,
        expected_commit=COMMIT,
    )
    return output, harness, capture, clock


def test_each_sample_calls_capture_once_without_fabricating_frames(
    tmp_path: Path,
) -> None:
    output, _, capture, _ = run_one_burst(tmp_path)

    frames = jsonl(output / "frames.jsonl")

    assert capture.call_count == 10
    assert [row["frame_id"] for row in frames] == [6, 7, 8, 9, 10]
    assert [row["global_frame_sequence"] for row in frames] == [1, 2, 3, 4, 5]
    assert [row["sequence_in_burst"] for row in frames] == [1, 2, 3, 4, 5]


def test_absolute_deadlines_do_not_accumulate_capture_duration() -> None:
    clock = FakeClock(current_ns=0)
    capture = FakeCaptureService(make_frames(5), clock=clock, duration_ns=30_000_000)
    harness = build_harness(capture=capture, clock=clock)

    batch = harness.capture_batch(frame_count=5, period_ns=125_000_000)

    assert [slot.deadline_ns for slot in batch.slots] == [
        0,
        125_000_000,
        250_000_000,
        375_000_000,
        500_000_000,
    ]
    assert [slot.capture_started_ns for slot in batch.slots] == [
        0,
        125_000_000,
        250_000_000,
        375_000_000,
        500_000_000,
    ]
    assert all(slot.lateness_ns == 0 for slot in batch.slots)


def test_lateness_and_deadline_overrun_are_reported(tmp_path: Path) -> None:
    output, _, _, _ = run_one_burst(tmp_path, capture_duration_ns=200_000_000)

    burst = jsonl(output / "bursts.jsonl")[0]
    frames = jsonl(output / "frames.jsonl")

    assert TechnicalFailureReason.DEADLINE_OVERRUN.value in cast(
        list[str], burst["technical_failure_reasons"]
    )
    assert max(cast(int, row["lateness_ns"]) for row in frames) >= 125_000_000


@pytest.mark.parametrize(
    ("replacement", "reason"),
    [
        (None, TechnicalFailureReason.CAPTURE_UNAVAILABLE),
        (RuntimeError("capture boom"), TechnicalFailureReason.CAPTURE_ERROR),
    ],
)
def test_capture_failure_invalidates_without_fabrication(
    tmp_path: Path,
    replacement: Frame | None | BaseException,
    reason: TechnicalFailureReason,
) -> None:
    frames: list[Frame | None | BaseException] = make_frames(10)
    frames[7] = replacement

    output, _, capture, _ = run_one_burst(tmp_path, frames=frames)
    burst = jsonl(output / "bursts.jsonl")[0]
    persisted = jsonl(output / "frames.jsonl")

    assert capture.call_count == 10
    assert reason.value in cast(list[str], burst["technical_failure_reasons"])
    assert persisted[2]["frame_id"] is None
    assert burst["physical_capture_count"] == 4
    assert burst["capture_complete"] is False
    assert burst["complete"] is False


def test_source_change_invalidates_burst(tmp_path: Path) -> None:
    frames = make_frames(10)
    frames[8] = make_frame(9, source="win32_hwnd:999")

    output, _, _, _ = run_one_burst(tmp_path, frames=frames)

    burst = jsonl(output / "bursts.jsonl")[0]
    assert TechnicalFailureReason.SOURCE_CHANGED.value in cast(
        list[str], burst["technical_failure_reasons"]
    )


def test_geometry_change_invalidates_burst(tmp_path: Path) -> None:
    frames = make_frames(10)
    frames[8] = make_frame(
        9,
        chart=np.zeros((7, 8, 4), dtype=np.uint8),
        price=np.zeros((7, 8, 4), dtype=np.uint8),
        chart_region=ChartRegion(x=0, y=10, width=8, height=7),
        price_region=ChartRegion(x=0, y=10, width=8, height=7),
    )

    output, _, _, _ = run_one_burst(tmp_path, frames=frames)

    burst = jsonl(output / "bursts.jsonl")[0]
    assert TechnicalFailureReason.GEOMETRY_CHANGED.value in cast(
        list[str], burst["technical_failure_reasons"]
    )


def test_non_monotonic_observed_timestamp_invalidates_burst(tmp_path: Path) -> None:
    frames = make_frames(10)
    frames[8] = make_frame(9, monotonic_ns=800)

    output, _, _, _ = run_one_burst(tmp_path, frames=frames)

    burst = jsonl(output / "bursts.jsonl")[0]
    assert TechnicalFailureReason.NON_MONOTONIC_TIMESTAMP.value in cast(
        list[str], burst["technical_failure_reasons"]
    )


def test_reused_ndarray_memory_invalidates_burst(tmp_path: Path) -> None:
    frames = make_frames(10)
    reused = np.zeros((6, 8, 4), dtype=np.uint8)
    frames[5] = make_frame(6, chart=reused)
    frames[6] = make_frame(7, chart=reused)

    output, _, _, _ = run_one_burst(tmp_path, frames=frames)

    burst = jsonl(output / "bursts.jsonl")[0]
    assert TechnicalFailureReason.FRAME_MEMORY_REUSED.value in cast(
        list[str], burst["technical_failure_reasons"]
    )


def test_reused_frame_object_is_not_used_to_complete_a_burst(tmp_path: Path) -> None:
    frames = make_frames(6)
    reused = make_frame(7)
    frames.extend([reused, reused, make_frame(9), make_frame(10)])

    output, _, _, _ = run_one_burst(tmp_path, frames=frames)

    burst = jsonl(output / "bursts.jsonl")[0]
    assert TechnicalFailureReason.FRAME_MEMORY_REUSED.value in cast(
        list[str], burst["technical_failure_reasons"]
    )


def test_duplicate_pixel_hashes_are_preserved_as_distinct_captures(
    tmp_path: Path,
) -> None:
    frames = make_frames(5)
    duplicate_content = np.full((6, 8, 4), 77, dtype=np.uint8)
    for frame_id in range(6, 11):
        frames.append(
            make_frame(
                frame_id,
                chart=duplicate_content.copy(),
                price=duplicate_content.copy(),
            )
        )

    output, _, _, _ = run_one_burst(tmp_path, frames=frames)
    persisted = jsonl(output / "frames.jsonl")
    descriptors = [
        cast(
            dict[str, object],
            cast(dict[str, object], row["images"])[
                "current_visual_price_input"
            ],
        )
        for row in persisted
    ]

    assert len({descriptor["pixel_sha256"] for descriptor in descriptors}) == 1
    assert len({descriptor["filename"] for descriptor in descriptors}) == 5
    assert [row["observed_monotonic_ns"] for row in persisted] == [
        600,
        700,
        800,
        900,
        1000,
    ]


def test_png_round_trip_hashes_and_manifest_mapping_are_exact(tmp_path: Path) -> None:
    output, _, _, _ = run_one_burst(tmp_path)
    frame = jsonl(output / "frames.jsonl")[0]
    images = cast(dict[str, object], frame["images"])
    descriptor = cast(dict[str, object], images["current_visual_price_input"])
    png_path = output / cast(str, descriptor["filename"])
    encoded = png_path.read_bytes()
    decoded = cv2.imdecode(np.frombuffer(encoded, np.uint8), cv2.IMREAD_UNCHANGED)

    assert decoded is not None
    assert decoded.shape == tuple(cast(list[int], descriptor["shape"]))
    assert str(decoded.dtype) == descriptor["dtype"]
    assert len(cast(str, descriptor["pixel_sha256"])) == 64
    assert len(cast(str, descriptor["png_sha256"])) == 64


def test_price_observation_is_exact_extractor_input_and_chart_is_preserved(
    tmp_path: Path,
) -> None:
    frames = make_frames(10)
    extractor = FakeExtractor()
    expected_price_images = [
        cast(Frame, frame).price_observation_image for frame in frames[5:]
    ]

    output, _, _, _ = run_one_burst(
        tmp_path,
        frames=frames,
        extractor=extractor,
    )
    persisted = jsonl(output / "frames.jsonl")

    assert all(
        actual is expected
        for actual, expected in zip(
            extractor.images,
            expected_price_images,
            strict=True,
        )
    )
    for row in persisted:
        images = cast(dict[str, object], row["images"])
        chart = cast(dict[str, object], images["chart"])
        price = cast(dict[str, object], images["current_visual_price_input"])
        assert chart["filename"] != price["filename"]
        assert chart["reuses_current_visual_price_png"] is False


def test_identical_chart_and_price_are_deduplicated_logically(tmp_path: Path) -> None:
    frames = make_frames(5)
    for frame_id in range(6, 11):
        chart = np.full((6, 8, 4), frame_id, dtype=np.uint8)
        frames.append(make_frame(frame_id, chart=chart, price=chart.copy()))

    output, _, _, _ = run_one_burst(tmp_path, frames=frames)
    persisted = jsonl(output / "frames.jsonl")

    for row in persisted:
        images = cast(dict[str, object], row["images"])
        chart = cast(dict[str, object], images["chart"])
        price = cast(dict[str, object], images["current_visual_price_input"])
        assert chart["filename"] == price["filename"]
        assert chart["reuses_current_visual_price_png"] is True


def test_extractor_failure_is_explicit_and_logged(tmp_path: Path) -> None:
    output, _, _, _ = run_one_burst(
        tmp_path,
        extractor=FakeExtractor(error=RuntimeError("extractor boom")),
    )

    burst = jsonl(output / "bursts.jsonl")[0]
    frames = jsonl(output / "frames.jsonl")
    failures = jsonl(output / "failures.jsonl")

    assert TechnicalFailureReason.EXTRACTOR_ERROR.value in cast(
        list[str], burst["technical_failure_reasons"]
    )
    assert all(row["current_visual_price"] is None for row in frames)
    assert any(
        row["reason"] == TechnicalFailureReason.EXTRACTOR_ERROR.value
        for row in failures
    )


def test_invalid_png_roundtrip_never_publishes_valid_image(tmp_path: Path) -> None:
    output, _, _, _ = run_one_burst(
        tmp_path,
        png_encoder=lambda image: b"not-a-png",
    )

    burst = jsonl(output / "bursts.jsonl")[0]
    frames = jsonl(output / "frames.jsonl")

    assert TechnicalFailureReason.PNG_ROUNDTRIP_FAILED.value in cast(
        list[str], burst["technical_failure_reasons"]
    )
    assert burst["evidence_complete"] is False
    assert burst["complete"] is False
    assert all(row["images"] is None for row in frames)
    assert not list((output / "bursts").rglob("*.png"))


def test_persistence_error_is_distinct_from_png_roundtrip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_write(*args, **kwargs) -> None:
        raise OSError("disk unavailable")

    monkeypatch.setattr(
        harness_module._SessionStore,  # noqa: SLF001 - failure-path audit.
        "publish_lossless_png",
        fail_write,
    )

    output, _, _, _ = run_one_burst(tmp_path)
    burst = jsonl(output / "bursts.jsonl")[0]

    assert TechnicalFailureReason.PERSISTENCE_ERROR.value in cast(
        list[str], burst["technical_failure_reasons"]
    )
    assert TechnicalFailureReason.PNG_ROUNDTRIP_FAILED.value not in cast(
        list[str], burst["technical_failure_reasons"]
    )


def test_wrong_expected_commit_fails_closed_before_output(tmp_path: Path) -> None:
    clock = FakeClock()
    capture = FakeCaptureService(make_frames(10), clock=clock)
    harness = build_harness(capture=capture, clock=clock)
    repository = tmp_path / "repository"
    repository.mkdir()
    output = tmp_path / "output"

    with pytest.raises(CalibrationHarnessError, match="no coincide"):
        harness.run(
            config=HarnessConfig(preflight_frames=5, candidate_bursts=1),
            output_directory=output,
            repository_root=repository,
            expected_commit="a" * 40,
        )

    assert not output.exists()
    assert capture.call_count == 0


def test_dirty_repository_fails_closed_before_output(tmp_path: Path) -> None:
    clock = FakeClock()
    capture = FakeCaptureService(make_frames(10), clock=clock)
    harness = build_harness(
        capture=capture,
        clock=clock,
        git=FakeGitProvider(dirty=True),
    )
    repository = tmp_path / "repository"
    repository.mkdir()

    with pytest.raises(CalibrationHarnessError, match="dirty"):
        harness.run(
            config=HarnessConfig(preflight_frames=5, candidate_bursts=1),
            output_directory=tmp_path / "output",
            repository_root=repository,
            expected_commit=COMMIT,
        )

    assert capture.call_count == 0


def test_output_inside_repository_is_rejected(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()

    with pytest.raises(CalibrationHarnessError, match="fuera del repositorio"):
        validate_external_output_directory(
            output_directory=repository / "calibration",
            repository_root=repository,
        )


def test_external_empty_output_is_allowed(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    output = tmp_path / "external" / "session"
    repository.mkdir()

    assert validate_external_output_directory(
        output_directory=output,
        repository_root=repository,
    ) == output.resolve()


def test_non_empty_external_output_is_rejected(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    output = tmp_path / "external"
    repository.mkdir()
    output.mkdir()
    (output / "existing.txt").write_text("do not overwrite", encoding="utf-8")

    with pytest.raises(CalibrationHarnessError, match="vacío"):
        validate_external_output_directory(
            output_directory=output,
            repository_root=repository,
        )


def test_session_metadata_contains_non_null_git_provenance(tmp_path: Path) -> None:
    output, _, _, _ = run_one_burst(tmp_path)

    metadata = json.loads((output / "session_metadata.json").read_text("utf-8"))

    assert metadata["source_commit"] == COMMIT
    assert metadata["expected_commit"] == COMMIT
    assert metadata["git"]["branch"] == "feat/visual-price-resolution"
    assert metadata["git"]["ahead"] == 0
    assert metadata["git"]["behind"] == 0
    assert metadata["fixed_edge_override"] is None
    assert metadata["critical_section"] == {
        "capture_only": True,
        "extractor": False,
        "filesystem": False,
        "gui": False,
        "png": False,
        "strategy": False,
    }


@pytest.mark.parametrize("shape", [(788, 1154, 4), (640, 941, 4)])
def test_nominal_and_resized_geometry_are_preserved(
    tmp_path: Path,
    shape: tuple[int, int, int],
) -> None:
    height, width, _ = shape
    frames: list[Frame | None | BaseException] = make_frames(5)
    for frame_id in range(6, 11):
        chart = np.full(shape, frame_id % 255, dtype=np.uint8)
        price = np.full(shape, (frame_id + 1) % 255, dtype=np.uint8)
        frames.append(
            make_frame(
                frame_id,
                chart=chart,
                price=price,
                chart_region=ChartRegion(x=0, y=100, width=width, height=height),
                price_region=ChartRegion(x=0, y=100, width=width, height=height),
            )
        )

    output, _, _, _ = run_one_burst(tmp_path, frames=frames)
    persisted = jsonl(output / "frames.jsonl")

    assert all(
        cast(dict[str, object], row["geometry"])["chart_array_shape"]
        == list(shape)
        for row in persisted
    )


def test_candidate_burst_never_receives_stationary_classification(
    tmp_path: Path,
) -> None:
    output, _, _, _ = run_one_burst(tmp_path)

    burst = jsonl(output / "bursts.jsonl")[0]
    frames = jsonl(output / "frames.jsonl")
    summary = json.loads((output / "summary.json").read_text("utf-8"))

    assert burst["candidate_only"] is True
    assert burst["ground_truth_classification"] is None
    assert all(row["ground_truth_classification"] is None for row in frames)
    assert summary["ground_truth_classification"] is None


def test_preflight_reports_measurements_without_acceptance_policy(
    tmp_path: Path,
) -> None:
    output, _, _, _ = run_one_burst(tmp_path)

    preflight = json.loads((output / "preflight.json").read_text("utf-8"))

    assert preflight["measurement_only"] is True
    assert preflight["campaign_acceptance_policy_applied"] is False
    assert preflight["requested_frames"] == 5
    assert preflight["available_frames"] == 5
    assert preflight["effective_fps"] == pytest.approx(8.0)
    assert preflight["five_frame_span_ns"]["median"] == 500_000_000


def test_critical_burst_section_does_not_extract_or_publish_png(
    tmp_path: Path,
) -> None:
    clock = FakeClock()
    extractor = FakeExtractor()
    output = tmp_path / "evidence"

    class AuditedCapture(FakeCaptureService):
        def capture_once(self) -> Frame | None:
            if self.call_count >= 5:
                assert extractor.images == []
                assert not list(output.rglob("*.png"))
            return super().capture_once()

    capture = AuditedCapture(make_frames(10), clock=clock)
    harness = build_harness(capture=capture, clock=clock, extractor=extractor)
    repository = tmp_path / "repository"
    repository.mkdir()

    harness.run(
        config=HarnessConfig(preflight_frames=5, candidate_bursts=1),
        output_directory=output,
        repository_root=repository,
        expected_commit=COMMIT,
    )

    assert len(extractor.images) == 5


def test_interrupt_inside_burst_is_persisted_as_incomplete(tmp_path: Path) -> None:
    frames: list[Frame | None | BaseException] = make_frames(5)
    frames.extend([make_frame(6), make_frame(7), KeyboardInterrupt()])

    output, _, capture, _ = run_one_burst(tmp_path, frames=frames)

    burst = jsonl(output / "bursts.jsonl")[0]
    summary = json.loads((output / "summary.json").read_text("utf-8"))

    assert capture.call_count == 8
    assert burst["technical_status"] == BurstTechnicalStatus.INCOMPLETE.value
    assert burst["complete"] is False
    assert burst["captured_slot_count"] == 2
    assert summary["status"] == "interrupted"


def test_interrupt_between_bursts_stops_cleanly(tmp_path: Path) -> None:
    class InterruptingClock(FakeClock):
        def sleep(self, seconds: float) -> None:
            if seconds == 1.0:
                raise KeyboardInterrupt
            super().sleep(seconds)

    clock = InterruptingClock()
    capture = FakeCaptureService(make_frames(15), clock=clock)
    harness = build_harness(capture=capture, clock=clock)
    repository = tmp_path / "repository"
    repository.mkdir()
    output = tmp_path / "evidence"

    result = harness.run(
        config=HarnessConfig(
            preflight_frames=5,
            candidate_bursts=2,
            inter_burst_delay_seconds=1.0,
        ),
        output_directory=output,
        repository_root=repository,
        expected_commit=COMMIT,
    )

    assert result.interrupted is True
    assert result.captured_bursts == 1
    assert json.loads((output / "summary.json").read_text("utf-8"))["status"] == (
        "interrupted"
    )


def test_global_and_burst_sequences_continue_across_candidate_bursts(
    tmp_path: Path,
) -> None:
    output, _, capture, _ = run_one_burst(tmp_path, candidate_bursts=2)

    bursts = jsonl(output / "bursts.jsonl")
    frames = jsonl(output / "frames.jsonl")

    assert capture.call_count == 15
    assert [row["burst_sequence"] for row in bursts] == [1, 2]
    assert len({row["burst_id"] for row in bursts}) == 2
    assert [row["global_frame_sequence"] for row in frames] == list(range(1, 11))
    assert [row["sequence_in_burst"] for row in frames] == [1, 2, 3, 4, 5] * 2


def test_replay_uses_persisted_png_deterministically(tmp_path: Path) -> None:
    extractor = FakeExtractor()
    output, _, _, _ = run_one_burst(tmp_path, extractor=extractor)
    frame = jsonl(output / "frames.jsonl")[0]
    replay_extractor = FakeExtractor()

    first = replay_current_visual_price_frame(
        session_directory=output,
        frame_payload=frame,
        extractor=replay_extractor,
    )
    second = replay_current_visual_price_frame(
        session_directory=output,
        frame_payload=frame,
        extractor=replay_extractor,
    )

    assert first == second
    assert np.array_equal(replay_extractor.images[0], replay_extractor.images[1])
    assert replay_extractor.images[0] is not replay_extractor.images[1]


def test_chart_fallback_is_the_exact_extractor_input(tmp_path: Path) -> None:
    frames = make_frames(5)
    expected: list[np.ndarray] = []
    for frame_id in range(6, 11):
        chart = np.full((6, 8, 4), frame_id, dtype=np.uint8)
        expected.append(chart)
        frame = make_frame(frame_id, chart=chart)
        frames.append(
            Frame(
                frame_id=frame.frame_id,
                timestamp=frame.timestamp,
                image=frame.image,
                price_observation_image=None,
                chart_region=frame.chart_region,
                price_observation_region=None,
                monotonic_timestamp_ns=frame.monotonic_timestamp_ns,
                source_key=frame.source_key,
            )
        )
    extractor = FakeExtractor()

    output, _, _, _ = run_one_burst(
        tmp_path,
        frames=frames,
        extractor=extractor,
    )
    persisted = jsonl(output / "frames.jsonl")

    assert all(
        actual is expected_image
        for actual, expected_image in zip(extractor.images, expected, strict=True)
    )
    assert all(
        cast(dict[str, object], row["images"])["price_observation_relation"]
        == "fallback_to_chart"
        for row in persisted
    )


def test_productive_extractor_uses_dynamic_resolver_without_fixed_edge() -> None:
    extractor = build_productive_extractor()

    assert isinstance(extractor, PocketOptionCurrentVisualPriceExtractor)
    assert isinstance(
        extractor._search_window_resolver,  # noqa: SLF001 - contract audit.
        PocketOptionCurrentVisualPriceSearchWindowResolver,
    )
    assert extractor._effective_chart_right_x is None  # noqa: SLF001
    assert extractor._right_band_ratio == 0.20  # noqa: SLF001
    assert extractor._label_zone_ratio == 0.25  # noqa: SLF001


@pytest.mark.parametrize(
    ("git", "diagnostic"),
    [
        (FakeGitProvider(branch=""), "detached"),
        (FakeGitProvider(), "40 caracteres"),
    ],
)
def test_invalid_formal_provenance_fails_closed(
    tmp_path: Path,
    git: FakeGitProvider,
    diagnostic: str,
) -> None:
    clock = FakeClock()
    capture = FakeCaptureService(make_frames(10), clock=clock)
    harness = build_harness(capture=capture, clock=clock, git=git)
    repository = tmp_path / "repository"
    repository.mkdir()
    expected = COMMIT if git.branch == "" else "short"

    with pytest.raises(CalibrationHarnessError, match=diagnostic):
        harness.run(
            config=HarnessConfig(preflight_frames=5, candidate_bursts=1),
            output_directory=tmp_path / "output",
            repository_root=repository,
            expected_commit=expected,
        )

    assert capture.call_count == 0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"frames_per_burst": 4},
        {"frames_per_burst": 11},
        {"target_fps": 0.0},
        {"target_fps": float("inf")},
        {"candidate_bursts": 0},
        {"preflight_frames": 4},
        {"inter_burst_delay_seconds": -0.1},
    ],
)
def test_harness_config_rejects_invalid_cli_semantics(
    kwargs: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        HarnessConfig(**kwargs)
