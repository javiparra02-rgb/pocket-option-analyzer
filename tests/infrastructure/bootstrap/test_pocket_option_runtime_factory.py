from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np
import pytest

from pocket_option_analyzer.domain.signals import (
    SignalDirection,
    SignalHistory,
)
from pocket_option_analyzer.infrastructure.bootstrap import (
    PocketOptionRuntimeFactory,
)
from pocket_option_analyzer.infrastructure.config import Settings
from pocket_option_analyzer.infrastructure.evidence import (
    FilesystemVisualEvidenceRecorder,
)
from pocket_option_analyzer.vision.models import ChartRegion
from pocket_option_analyzer.vision.services import (
    ChartRegionExtractor,
    FixedChartRegionExtractor,
    PocketOptionChartRegionExtractor,
    PocketOptionPriceObservationRegionExtractor,
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


def test_pocket_option_runtime_factory_creates_runtime_with_injected_capture_service() -> (  # noqa: E501
    None
):

    history = SignalHistory()
    frame = _frame()

    runtime_service = PocketOptionRuntimeFactory.create_runtime_service(
        capture_service=FakeCaptureService(
            frames=[
                frame,
            ],
        ),
        signal_history=history,
        signal_file_path=None,
        interval_seconds=0.0,
    )

    record = runtime_service.run_once()

    assert record is not None
    assert history.latest() is record
    assert record.signal.direction is SignalDirection.NONE
    assert record.created_at is frame.captured_at
    assert record.source == "captured_frame_visual_analysis"


def test_pocket_option_runtime_factory_writes_jsonl_when_path_is_configured(
    tmp_path,
) -> None:

    history = SignalHistory()
    file_path = tmp_path / "signals" / "signals.jsonl"

    runtime_service = PocketOptionRuntimeFactory.create_runtime_service(
        capture_service=FakeCaptureService(
            frames=[
                _frame(),
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


def test_fixed_chart_region_extractor_preserves_configured_region() -> None:

    configured_region = ChartRegion(
        x=10,
        y=20,
        width=500,
        height=400,
    )

    extractor = FixedChartRegionExtractor(
        region=configured_region,
    )

    image = np.zeros(
        (
            100,
            200,
            3,
        ),
        dtype=np.uint8,
    )

    result = extractor.extract(
        image=image,
    )

    assert result is configured_region
    assert result.x == 10
    assert result.y == 20
    assert result.width == 500
    assert result.height == 400

    assert not result.fits_within(
        image_width=200,
        image_height=100,
    )


def test_pocket_option_chart_region_extractor_returns_candle_chart_area() -> None:

    extractor = PocketOptionChartRegionExtractor()

    image = np.zeros(
        (
            900,
            1600,
            3,
        ),
        dtype=np.uint8,
    )

    region = extractor.extract(
        image=image,
    )

    assert region.x == 0
    assert region.y == 90
    assert region.width == 1376
    assert region.height == 675
    assert region.bottom == 765

    assert region.fits_within(
        image_width=1600,
        image_height=900,
    )


def test_pocket_option_runtime_factory_disables_roi_debug_by_default() -> None:

    capture_service = PocketOptionRuntimeFactory.create_capture_service(
        window_title="Pocket Option",
        chart_region=ChartRegion(
            x=0,
            y=0,
            width=100,
            height=100,
        ),
    )

    assert capture_service is not None


def test_pocket_option_runtime_factory_configures_price_observation_region() -> None:

    capture_service = PocketOptionRuntimeFactory.create_capture_service()

    extractor = capture_service._price_observation_region_extractor

    assert isinstance(
        extractor,
        PocketOptionPriceObservationRegionExtractor,
    )
    assert extractor._bottom_extension_ratio == 0.0


def test_pocket_option_runtime_factory_can_enable_roi_debug(
    tmp_path,
) -> None:

    capture_service = PocketOptionRuntimeFactory.create_capture_service(
        window_title="Pocket Option",
        chart_region=ChartRegion(
            x=0,
            y=0,
            width=100,
            height=100,
        ),
        debug_roi_directory=tmp_path,
    )

    assert capture_service is not None


def test_pocket_option_chart_region_extractor_excludes_lower_indicators() -> None:

    extractor = PocketOptionChartRegionExtractor()

    image = np.zeros(
        (
            1000,
            1600,
            3,
        ),
        dtype=np.uint8,
    )

    region = extractor.extract(
        image=image,
    )

    assert region.y == 100
    assert region.width == 1376
    assert region.height == 750
    assert region.y + region.height == 850


@pytest.mark.parametrize(
    "region",
    [
        ChartRegion(
            x=-1,
            y=0,
            width=100,
            height=100,
        ),
        ChartRegion(
            x=0,
            y=-1,
            width=100,
            height=100,
        ),
        ChartRegion(
            x=0,
            y=0,
            width=0,
            height=100,
        ),
        ChartRegion(
            x=0,
            y=0,
            width=100,
            height=0,
        ),
    ],
    ids=[
        "negative_x",
        "negative_y",
        "zero_width",
        "zero_height",
    ],
)
def test_fixed_chart_region_extractor_rejects_invalid_configuration(
    region: ChartRegion,
) -> None:

    with pytest.raises(
        ValueError,
        match="Fixed chart region",
    ):
        FixedChartRegionExtractor(
            region=region,
        )


@pytest.mark.parametrize(
    (
        "top_ratio",
        "right_ratio",
        "bottom_ratio",
        "expected_message",
    ),
    [
        (
            -0.01,
            0.14,
            0.15,
            "top_ratio",
        ),
        (
            1.0,
            0.14,
            0.15,
            "top_ratio",
        ),
        (
            0.10,
            -0.01,
            0.15,
            "right_ratio",
        ),
        (
            0.10,
            1.0,
            0.15,
            "right_ratio",
        ),
        (
            0.10,
            0.14,
            -0.01,
            "bottom_ratio",
        ),
        (
            0.10,
            0.14,
            1.0,
            "bottom_ratio",
        ),
        (
            float("nan"),
            0.14,
            0.15,
            "top_ratio",
        ),
        (
            0.10,
            float("inf"),
            0.15,
            "right_ratio",
        ),
    ],
    ids=[
        "negative_top",
        "full_top",
        "negative_right",
        "full_right",
        "negative_bottom",
        "full_bottom",
        "nan_top",
        "infinite_right",
    ],
)
def test_pocket_option_chart_region_extractor_rejects_invalid_ratio(
    top_ratio: float,
    right_ratio: float,
    bottom_ratio: float,
    expected_message: str,
) -> None:

    with pytest.raises(
        ValueError,
        match=expected_message,
    ):
        PocketOptionChartRegionExtractor(
            top_ratio=top_ratio,
            right_ratio=right_ratio,
            bottom_ratio=bottom_ratio,
        )


@pytest.mark.parametrize(
    (
        "top_ratio",
        "bottom_ratio",
    ),
    [
        (
            0.50,
            0.50,
        ),
        (
            0.75,
            0.30,
        ),
    ],
    ids=[
        "exact_full_height",
        "exceeds_full_height",
    ],
)
def test_pocket_option_chart_region_extractor_rejects_vertical_ratio_sum(
    top_ratio: float,
    bottom_ratio: float,
) -> None:

    with pytest.raises(
        ValueError,
        match="sum to less than one",
    ):
        PocketOptionChartRegionExtractor(
            top_ratio=top_ratio,
            bottom_ratio=bottom_ratio,
        )


def test_pocket_option_chart_region_extractor_accepts_zero_ratios() -> None:

    extractor = PocketOptionChartRegionExtractor(
        top_ratio=0.0,
        right_ratio=0.0,
        bottom_ratio=0.0,
    )

    image = np.zeros(
        (
            100,
            200,
            3,
        ),
        dtype=np.uint8,
    )

    result = extractor.extract(
        image=image,
    )

    assert result == ChartRegion(
        x=0,
        y=0,
        width=200,
        height=100,
    )

    assert result.fits_within(
        image_width=200,
        image_height=100,
    )


def test_runtime_factory_keeps_visual_evidence_disabled_by_default() -> None:
    runtime = PocketOptionRuntimeFactory.create_runtime_service(
        capture_service=FakeCaptureService(frames=[]),
        signal_file_path=None,
        observation_file_path=None,
        settings=Settings(_env_file=None, visual_evidence_directory=None),
    )

    pipeline = runtime._loop_service._analysis_use_case._pipeline
    assert pipeline._visual_evidence_recorder is None


def test_runtime_factory_uses_opt_in_visual_evidence_setting(tmp_path) -> None:
    evidence_directory = tmp_path / "evidence"
    runtime = PocketOptionRuntimeFactory.create_runtime_service(
        capture_service=FakeCaptureService(frames=[]),
        signal_file_path=None,
        observation_file_path=tmp_path / "strategy_observations.jsonl",
        settings=Settings(
            _env_file=None,
            visual_evidence_directory=evidence_directory,
            app_version="0.1.0-test",
        ),
    )

    pipeline = runtime._loop_service._analysis_use_case._pipeline
    recorder = pipeline._visual_evidence_recorder
    assert isinstance(recorder, FilesystemVisualEvidenceRecorder)
    assert recorder.directory == evidence_directory


def test_runtime_factory_wires_opt_in_identity_evidence_policy(tmp_path) -> None:
    evidence_directory = tmp_path / "evidence"
    runtime = PocketOptionRuntimeFactory.create_runtime_service(
        capture_service=FakeCaptureService(frames=[]),
        signal_file_path=None,
        observation_file_path=None,
        settings=Settings(
            _env_file=None,
            visual_evidence_directory=evidence_directory,
            visual_identity_evidence_enabled=True,
            visual_identity_evidence_ring_buffer_size=45,
            visual_identity_evidence_pre_event_trace_count=7,
            visual_identity_evidence_intensive_png=True,
            visual_identity_evidence_checkpoint_interval_frames=60,
        ),
    )

    pipeline = runtime._loop_service._analysis_use_case._pipeline
    recorder = pipeline._identity_evidence_recorder
    assert recorder is pipeline._visual_evidence_recorder
    assert recorder._identity_config.ring_buffer_size == 45
    assert recorder._identity_config.pre_event_trace_count == 7
    assert recorder._identity_config.png_mode.value == "all_frames"
    assert recorder._identity_config.checkpoint_interval_frames == 60


def test_runtime_factory_rejects_identity_evidence_without_root() -> None:
    with pytest.raises(ValueError, match="VISUAL_EVIDENCE_DIRECTORY"):
        PocketOptionRuntimeFactory.create_runtime_service(
            capture_service=FakeCaptureService(frames=[]),
            signal_file_path=None,
            observation_file_path=None,
            settings=Settings(
                _env_file=None,
                visual_evidence_directory=None,
                visual_identity_evidence_enabled=True,
            ),
        )


@pytest.mark.parametrize(
    "extractor",
    [
        FixedChartRegionExtractor(
            region=ChartRegion(
                x=0,
                y=0,
                width=100,
                height=100,
            )
        ),
        PocketOptionChartRegionExtractor(),
    ],
    ids=[
        "fixed_region",
        "pocket_option_region",
    ],
)
@pytest.mark.parametrize(
    "image",
    [
        np.empty(
            (
                0,
                100,
                3,
            ),
            dtype=np.uint8,
        ),
        np.empty(
            (
                100,
                0,
                4,
            ),
            dtype=np.uint8,
        ),
        np.zeros(
            (
                100,
                100,
            ),
            dtype=np.uint8,
        ),
        np.zeros(
            (
                100,
                100,
                2,
            ),
            dtype=np.uint8,
        ),
        np.zeros(
            (
                100,
                100,
                3,
            ),
            dtype=np.float32,
        ),
    ],
    ids=[
        "zero_height",
        "zero_width",
        "two_dimensions",
        "unsupported_channels",
        "unsupported_dtype",
    ],
)
def test_chart_region_extractors_reject_invalid_images(
    extractor: ChartRegionExtractor,
    image: np.ndarray,
) -> None:

    with pytest.raises(
        ValueError,
        match="valid uint8 BGR or BGRA image",
    ):
        extractor.extract(
            image=image,
        )
