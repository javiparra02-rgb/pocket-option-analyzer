from __future__ import annotations

import numpy as np
import pytest
from test_capture_service import (
    FakeCapture,
    FakeFinder,
    FakeReader,
    FakeRegionExtractor,
)

from pocket_option_analyzer.infrastructure.capture.services import (
    CaptureService,
    FrameBuffer,
    FrameFactory,
)
from pocket_option_analyzer.vision.models import ChartRegion


@pytest.mark.parametrize("enabled", [False, True])
def test_context_is_from_same_acquisition_and_opt_in_only(enabled):
    image = np.arange(200 * 200 * 3, dtype=np.uint8).reshape(200, 200, 3)
    capture = FakeCapture(image)
    service = CaptureService(
        FakeFinder(),
        FakeReader(),
        capture,
        FakeRegionExtractor(),
        FrameFactory(),
        FrameBuffer(),
        observational_evidence_enabled=enabled,
        instrument_context_region=ChartRegion(5, 0, 80, 12),
        observational_frame_byte_limit=33000,
    )
    frame = service.capture_once()
    assert capture.capture_calls == 1
    assert np.array_equal(frame.image, image[20:120, 20:120])
    if enabled:
        assert np.array_equal(frame.instrument_context_image, image[0:12, 5:85])
        saved = frame.instrument_context_image.copy()
        image[:] = 0
        assert np.array_equal(frame.instrument_context_image, saved)
        data = frame.capture_metadata
        assert data["call_started_monotonic_ns"] <= data["call_finished_monotonic_ns"]
        assert data["quote_effective_at"] is None
        assert data["instrument_identity"] == "UNKNOWN"
    else:
        assert frame.instrument_context_image is frame.capture_metadata is None


def test_out_of_bounds_context_is_unknown_not_an_extra_capture():
    capture = FakeCapture()
    service = CaptureService(
        FakeFinder(),
        FakeReader(),
        capture,
        FakeRegionExtractor(),
        FrameFactory(),
        FrameBuffer(),
        observational_evidence_enabled=True,
        instrument_context_region=ChartRegion(500, 0, 80, 12),
    )
    frame = service.capture_once()
    assert capture.capture_calls == 1
    assert frame.instrument_context_image is None
    assert frame.capture_metadata["context_region"] is None


def test_context_copy_is_rejected_before_exceeding_pixel_budget():
    capture = FakeCapture()
    service = CaptureService(
        FakeFinder(),
        FakeReader(),
        capture,
        FakeRegionExtractor(),
        FrameFactory(),
        FrameBuffer(),
        observational_evidence_enabled=True,
        instrument_context_region=ChartRegion(0, 0, 200, 200),
        observational_frame_byte_limit=30000,  # Exactly the existing 100x100x3 ROI
    )
    frame = service.capture_once()
    assert frame.instrument_context_image is None
    assert not frame.capture_metadata["context_byte_budget_satisfied"]
    assert capture.capture_calls == 1
