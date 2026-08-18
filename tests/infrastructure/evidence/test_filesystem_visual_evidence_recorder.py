from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import get_type_hints

import cv2
import numpy as np
import pytest

from pocket_option_analyzer.application.evidence import (
    VisualEvidenceAssociation,
    VisualEvidencePhase,
    VisualEvidenceRecorder,
    VisualFrameEvidence,
)
from pocket_option_analyzer.application.strategy import (
    VisualPriceReference,
    VisualPriceReferenceResult,
    VisualPriceReferenceStatus,
)
from pocket_option_analyzer.infrastructure.evidence import (
    FilesystemVisualEvidenceRecorder,
    VisualEvidenceSerializer,
)
from pocket_option_analyzer.vision.models import (
    CandleCandidate,
    CandleCandidateDecision,
    CandleCandidateTrace,
    CandleColor,
    CandleDetectionTrace,
    CandleFilterConfigurationTrace,
    CandleGeometry,
    CandleMergeTrace,
    CandleSeries,
    CandleSeriesMembershipExclusion,
    CandleSeriesMembershipExclusionReason,
    CandleSeriesMembershipGapTrace,
    CandleSeriesMembershipRunTrace,
    CandleSeriesMembershipStatus,
    CandleSeriesMembershipTrace,
    CandleType,
    ChartRegion,
    ClassifiedCandle,
    CurrentVisualPriceDetectionTrace,
    CurrentVisualPriceExtraction,
    CurrentVisualPriceRejectionCounts,
    CurrentVisualPriceStatus,
    FinalCandleTrace,
    MarketAnalysis,
    TrendDirection,
)
from pocket_option_analyzer.vision.models.candle_detection_trace import (
    CandleWidthDecisionReason,
)

FIXED_NOW = datetime(2026, 8, 17, 20, 0, tzinfo=UTC)
FRAME_TIMESTAMP = datetime(2026, 8, 17, 19, 12, 34, 567890, tzinfo=UTC)


def _filter_configuration() -> CandleFilterConfigurationTrace:
    return CandleFilterConfigurationTrace(
        min_area=8,
        min_width=1,
        min_height=3,
        max_width=40,
        max_height=500,
        min_relative_width=0.5,
        max_relative_width=1.8,
        width_bucket_size=2,
        anchor_min_height_ratio=0.5,
        same_column_center_ratio=0.8,
        max_candidates=60,
    )


def _candidate_trace(
    candidate_id: str,
    *,
    x: int,
    decisions: tuple[CandleCandidateDecision, ...],
    merged_from: tuple[str, ...] = (),
    merged_into: str | None = None,
) -> CandleCandidateTrace:
    has_width_decision = any(
        decision
        in (
            CandleCandidateDecision.WIDTH_ACCEPTED,
            CandleCandidateDecision.REJECTED_WIDTH,
        )
        for decision in decisions
    )
    return CandleCandidateTrace(
        candidate_id=candidate_id,
        x=x,
        y=10,
        width=5,
        height=30,
        area=150,
        color=CandleColor.WHITE,
        decisions=decisions,
        dominant_width=5.0,
        width_decision_reason=(
            CandleWidthDecisionReason.WITHIN_DOMINANT_RANGE
            if has_width_decision
            else None
        ),
        merged_from=merged_from,
        merged_into=merged_into,
    )


def _candle_trace() -> CandleDetectionTrace:
    candidates = (
        _candidate_trace(
            "c1",
            x=10,
            decisions=(
                CandleCandidateDecision.SEGMENTED,
                CandleCandidateDecision.DIMENSION_ACCEPTED,
                CandleCandidateDecision.WIDTH_ACCEPTED,
                CandleCandidateDecision.RETURNED,
            ),
        ),
        _candidate_trace(
            "s1",
            x=20,
            decisions=(
                CandleCandidateDecision.SEGMENTED,
                CandleCandidateDecision.DIMENSION_ACCEPTED,
                CandleCandidateDecision.WIDTH_ACCEPTED,
                CandleCandidateDecision.MERGED,
            ),
            merged_into="m1",
        ),
        _candidate_trace(
            "s2",
            x=21,
            decisions=(
                CandleCandidateDecision.SEGMENTED,
                CandleCandidateDecision.DIMENSION_ACCEPTED,
                CandleCandidateDecision.WIDTH_ACCEPTED,
                CandleCandidateDecision.MERGED,
            ),
            merged_into="m1",
        ),
        _candidate_trace(
            "m1",
            x=20,
            decisions=(
                CandleCandidateDecision.MERGE_RESULT,
                CandleCandidateDecision.RETURNED,
            ),
            merged_from=("s1", "s2"),
        ),
    )
    return CandleDetectionTrace(
        candidates=candidates,
        merges=(
            CandleMergeTrace(
                result_candidate_id="m1",
                source_candidate_ids=("s1", "s2"),
                maximum_center_distance=4.0,
            ),
        ),
        returned_candidate_ids=("c1", "m1"),
        dominant_width=5.0,
        maximum_returned_candidates=60,
        filter_configuration=_filter_configuration(),
        final_candles=(
            FinalCandleTrace(
                candidate_id="c1",
                source_candidate_ids=("c1",),
                ordinal=0,
                x=10,
                y=10,
                width=5,
                height=30,
                area=150,
                color=CandleColor.WHITE,
                candle_type=CandleType.BULLISH,
                geometry=CandleGeometry(10, 14, 25, 39),
                is_latest=False,
                is_anchor=True,
                anchor_index=0,
                anchor_exclusion_reason=None,
            ),
            FinalCandleTrace(
                candidate_id="m1",
                source_candidate_ids=("s1", "s2"),
                ordinal=1,
                x=20,
                y=12,
                width=5,
                height=30,
                area=150,
                color=CandleColor.RED,
                candle_type=CandleType.BEARISH,
                geometry=CandleGeometry(12, 16, 28, 41),
                is_latest=True,
                is_anchor=False,
            ),
        ),
    )


def _price_trace() -> CurrentVisualPriceDetectionTrace:
    return CurrentVisualPriceDetectionTrace(
        status=CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE,
        image_width=100,
        image_height=20,
        effective_chart_right_x=90,
        effective_chart_right_source="configured",
        band_start=80,
        band_end=100,
        band_width=20,
        safe_top=2,
        safe_bottom=18,
        masked_pixel_count=0,
        candidates=(),
        rejection_counts=CurrentVisualPriceRejectionCounts(
            rows_without_mask_pixels=20,
            rows_with_mask_pixels=0,
            rejected_by_coverage=0,
            rejected_by_span=0,
            rejected_by_right_edge_gap=0,
            qualifying_rows=0,
            candidate_groups=0,
            rejected_by_group_height=0,
        ),
    )


def _membership_trace() -> CandleSeriesMembershipTrace:
    return CandleSeriesMembershipTrace(
        status=CandleSeriesMembershipStatus.AVAILABLE,
        evaluated_candidate_ids=("c1", "m1"),
        member_candidate_ids=("c1",),
        excluded_candidates=(
            CandleSeriesMembershipExclusion(
                candidate_id="m1",
                reason=(
                    CandleSeriesMembershipExclusionReason.HORIZONTAL_OUTLIER
                ),
                horizontal_gap_px=10.0,
                diagnostic="candidate_isolated_from_supported_lattice",
            ),
        ),
        evaluated_gaps=(
            CandleSeriesMembershipGapTrace(
                left_candidate_id="c1",
                right_candidate_id="m1",
                horizontal_gap_px=10.0,
                estimated_slot_count=2,
                horizontal_consistent=False,
            ),
        ),
        estimated_pitch_px=5.0,
        candidate_runs=(
            CandleSeriesMembershipRunTrace(
                run_id="run_000",
                candidate_ids=("c1",),
                selected=True,
            ),
            CandleSeriesMembershipRunTrace(
                run_id="run_001",
                candidate_ids=("m1",),
                selected=False,
            ),
        ),
        selected_run_support=1,
        latest_candidate_id="c1",
        diagnostic="dominant_supported_run_selected",
    )


def _series() -> CandleSeries:
    return CandleSeries(
        candles=(
            ClassifiedCandle(
                candidate=CandleCandidate(
                    x=10,
                    y=10,
                    width=5,
                    height=30,
                    area=150,
                    color=CandleColor.WHITE,
                    geometry=CandleGeometry(10, 14, 25, 39),
                ),
                candle_type=CandleType.BULLISH,
            ),
            ClassifiedCandle(
                candidate=CandleCandidate(
                    x=20,
                    y=12,
                    width=5,
                    height=30,
                    area=150,
                    color=CandleColor.RED,
                    geometry=CandleGeometry(12, 16, 28, 41),
                ),
                candle_type=CandleType.BEARISH,
            ),
        )
    )


def _reference_result() -> VisualPriceReferenceResult:
    return VisualPriceReferenceResult(
        reference=VisualPriceReference(
            value=0.45,
            anchor_shape=(("bullish", 1.0, 0.8, 0.4, 0.0),),
        ),
        status=VisualPriceReferenceStatus.OK,
        anchor_count=1,
        latest_candle_type="bearish",
        latest_candidate_x=20,
        latest_candidate_y=12,
        close_roi_y=28,
        anchor_top_roi_y=10,
        anchor_bottom_roi_y=39,
        raw_normalized_close=0.45,
    )


def _image(channels: int = 3, *, seed: int = 7) -> np.ndarray:
    generator = np.random.default_rng(seed)
    return generator.integers(
        0,
        256,
        size=(48, 64, channels),
        dtype=np.uint8,
    )


def _evidence(
    *,
    image: np.ndarray | None = None,
    price_image: np.ndarray | None = None,
    frame_id: int = 123,
    timestamp: datetime = FRAME_TIMESTAMP,
    candle_trace_override: CandleDetectionTrace | None = None,
) -> VisualFrameEvidence:
    chart_image = image if image is not None else _image()
    candle_trace = candle_trace_override or _candle_trace()
    price_trace = _price_trace()
    extraction = CurrentVisualPriceExtraction(
        price=None,
        status=CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE,
        candidate_count=0,
        diagnostic="no_qualifying_rows",
    )
    chart_region = ChartRegion(x=10, y=20, width=64, height=48)
    price_region = ChartRegion(x=10, y=20, width=64, height=48)
    market_analysis = MarketAnalysis(
        series=_series(),
        trend=TrendDirection.BEARISH,
        current_visual_price=extraction,
        chart_region=chart_region,
        price_observation_region=price_region,
        candle_detection_trace=candle_trace,
        current_visual_price_detection_trace=price_trace,
    )
    return VisualFrameEvidence(
        frame_id=frame_id,
        frame_timestamp=timestamp,
        image=chart_image,
        price_observation_image=price_image,
        chart_region=chart_region,
        price_observation_region=price_region,
        source="captured_frame_visual_analysis",
        market_analysis=market_analysis,
        current_visual_price=extraction,
        visual_price_reference_result=_reference_result(),
        candle_detection_trace=candle_trace,
        current_visual_price_detection_trace=price_trace,
    )


def _entry(snapshot: datetime = FRAME_TIMESTAMP) -> VisualEvidenceAssociation:
    return VisualEvidenceAssociation(
        snapshot_id=snapshot.isoformat(),
        phase=VisualEvidencePhase.ENTRY,
        observed_at=snapshot,
        resolve_at=snapshot + timedelta(seconds=10),
        candle_interval_started_at=snapshot,
    )


def _exit(snapshot: datetime = FRAME_TIMESTAMP) -> VisualEvidenceAssociation:
    return VisualEvidenceAssociation(
        snapshot_id=snapshot.isoformat(),
        phase=VisualEvidencePhase.EXIT,
        observed_at=snapshot,
        resolve_at=snapshot + timedelta(seconds=10),
        resolved_at=snapshot + timedelta(seconds=11),
    )


def _store(
    directory: Path,
    *,
    png_encoder=None,
) -> FilesystemVisualEvidenceRecorder:
    return FilesystemVisualEvidenceRecorder(
        directory,
        application_version="0.1.0-test",
        observation_jsonl_path=Path("logs/strategy_observations.jsonl"),
        clock=lambda: FIXED_NOW,
        png_encoder=png_encoder,
    )


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _manifest(directory: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in (directory / "manifest.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line
    ]


def _frame_directory(directory: Path) -> Path:
    frames = [path for path in (directory / "frames").iterdir() if path.is_dir()]
    assert len(frames) == 1
    return frames[0]


def test_store_initialization_creates_session_structure(tmp_path: Path) -> None:
    directory = tmp_path / "evidence"

    _store(directory)

    assert (directory / "session_metadata.json").is_file()
    assert (directory / "manifest.jsonl").is_file()
    assert (directory / "failures.jsonl").is_file()
    assert (directory / "frames").is_dir()
    assert (directory / "snapshots").is_dir()


def test_entry_creates_frame_and_small_snapshot_pointer(tmp_path: Path) -> None:
    directory = tmp_path / "evidence"
    evidence = _evidence()
    association = _entry()

    _store(directory).record_frame(evidence, (association,))

    frame_directory = _frame_directory(directory)
    snapshot_key = FilesystemVisualEvidenceRecorder.snapshot_key(
        association.snapshot_id
    )
    entry = _read_json(directory / "snapshots" / snapshot_key / "entry.json")
    assert (frame_directory / "frame.json").is_file()
    assert (frame_directory / "chart.png").is_file()
    assert entry["snapshot_id"] == association.snapshot_id
    assert entry["frame_key"] == frame_directory.name
    assert "analysis" not in entry


def test_exit_creates_exit_pointer_with_resolved_at(tmp_path: Path) -> None:
    directory = tmp_path / "evidence"
    association = _exit()

    _store(directory).record_frame(_evidence(), (association,))

    snapshot_key = FilesystemVisualEvidenceRecorder.snapshot_key(
        association.snapshot_id
    )
    payload = _read_json(directory / "snapshots" / snapshot_key / "exit.json")
    assert payload["phase"] == "exit"
    assert payload["resolved_at"] == association.resolved_at.isoformat()


def test_reference_only_exit_requires_no_primary_resolution_data(
    tmp_path: Path,
) -> None:
    association = _exit()
    directory = tmp_path / "evidence"

    _store(directory).record_frame(_evidence(), (association,))

    assert _manifest(directory)[0]["snapshot_id"] == association.snapshot_id
    assert _manifest(directory)[0]["phase"] == "exit"


def test_multiple_exits_encode_one_physical_frame(tmp_path: Path) -> None:
    calls = 0

    def encoder(image: np.ndarray) -> bytes:
        nonlocal calls
        calls += 1
        return FilesystemVisualEvidenceRecorder._default_png_encoder(image)

    directory = tmp_path / "evidence"
    associations = tuple(
        _exit(FRAME_TIMESTAMP + timedelta(seconds=offset))
        for offset in range(3)
    )

    _store(directory, png_encoder=encoder).record_frame(
        _evidence(),
        associations,
    )

    manifest = _manifest(directory)
    png_size = next((directory / "frames").rglob("*.png")).stat().st_size

    assert calls == 1
    assert len(list((directory / "frames").iterdir())) == 1
    assert len(manifest) == 3
    assert sum(event["frame_created"] for event in manifest) == 1
    assert sum(event["png_bytes_written"] for event in manifest) == png_size


def test_exit_and_entry_share_one_frame_package(tmp_path: Path) -> None:
    directory = tmp_path / "evidence"

    _store(directory).record_frame(
        _evidence(),
        (_exit(), _entry(FRAME_TIMESTAMP + timedelta(seconds=20))),
    )

    assert len(list((directory / "frames").iterdir())) == 1
    assert {event["phase"] for event in _manifest(directory)} == {
        "entry",
        "exit",
    }


def test_snapshot_key_is_windows_safe_and_deterministic() -> None:
    snapshot_id = "2026-08-17T19:12:34.567890+00:00"

    first = FilesystemVisualEvidenceRecorder.snapshot_key(snapshot_id)
    second = FilesystemVisualEvidenceRecorder.snapshot_key(snapshot_id)

    assert first == second
    assert ":" not in first
    assert "+" not in first
    assert first.endswith(hashlib.sha256(snapshot_id.encode()).hexdigest()[:12])


def test_frame_key_is_deterministic_and_traces_runtime_frame_id() -> None:
    evidence = _evidence(frame_id=123)

    key = FilesystemVisualEvidenceRecorder.frame_key(evidence)

    assert key == "frame_00000123_20260817T191234567890Z"


def test_snapshot_original_is_preserved_in_association_and_manifest(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "evidence"
    association = _entry()

    _store(directory).record_frame(_evidence(), (association,))

    key = FilesystemVisualEvidenceRecorder.snapshot_key(association.snapshot_id)
    assert (
        _read_json(directory / "snapshots" / key / "entry.json")["snapshot_id"]
        == association.snapshot_id
    )
    assert _manifest(directory)[0]["snapshot_id"] == association.snapshot_id


@pytest.mark.parametrize("channels", [3, 4], ids=["bgr", "bgra"])
def test_png_round_trip_is_lossless(
    tmp_path: Path,
    channels: int,
) -> None:
    image = _image(channels)
    directory = tmp_path / f"evidence-{channels}"

    _store(directory).record_frame(_evidence(image=image), (_entry(),))

    decoded = cv2.imread(
        str(_frame_directory(directory) / "chart.png"),
        cv2.IMREAD_UNCHANGED,
    )
    assert np.array_equal(decoded, image)


def test_equal_price_roi_reuses_chart_png(tmp_path: Path) -> None:
    image = _image()
    directory = tmp_path / "evidence"

    _store(directory).record_frame(
        _evidence(image=image, price_image=image.copy()),
        (_entry(),),
    )

    frame_directory = _frame_directory(directory)
    metadata = _read_json(frame_directory / "frame.json")
    assert not (frame_directory / "price_observation.png").exists()
    assert metadata["images"]["price_observation"]["reuses_chart_png"] is True
    assert (
        metadata["images"]["price_observation"]["filename"]
        == metadata["images"]["chart"]["filename"]
    )


def test_distinct_price_roi_gets_separate_png(tmp_path: Path) -> None:
    directory = tmp_path / "evidence"

    _store(directory).record_frame(
        _evidence(image=_image(seed=1), price_image=_image(seed=2)),
        (_entry(),),
    )

    frame_directory = _frame_directory(directory)
    metadata = _read_json(frame_directory / "frame.json")
    assert (frame_directory / "price_observation.png").is_file()
    assert metadata["images"]["price_observation"]["reuses_chart_png"] is False


def test_equal_pixels_from_different_regions_get_separate_png(
    tmp_path: Path,
) -> None:
    image = _image()
    evidence = _evidence(image=image, price_image=image.copy())
    evidence.price_observation_region = ChartRegion(
        x=10,
        y=21,
        width=64,
        height=48,
    )
    directory = tmp_path / "evidence"

    _store(directory).record_frame(evidence, (_entry(),))

    frame_directory = _frame_directory(directory)
    metadata = _read_json(frame_directory / "frame.json")
    assert (frame_directory / "price_observation.png").is_file()
    assert metadata["images"]["price_observation"]["reuses_chart_png"] is False


def test_png_hashes_match_persisted_bytes(tmp_path: Path) -> None:
    directory = tmp_path / "evidence"
    _store(directory).record_frame(_evidence(), (_entry(),))
    frame_directory = _frame_directory(directory)
    metadata = _read_json(frame_directory / "frame.json")
    png_bytes = (frame_directory / "chart.png").read_bytes()

    assert metadata["images"]["chart"]["sha256"] == hashlib.sha256(
        png_bytes
    ).hexdigest()


def test_frame_metadata_contains_capture_geometry_and_array_types(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "evidence"
    _store(directory).record_frame(_evidence(), (_entry(),))
    metadata = _read_json(_frame_directory(directory) / "frame.json")

    assert metadata["geometry"]["chart_region"]["x"] == 10
    assert metadata["arrays"]["chart"]["shape"] == [48, 64, 3]
    assert metadata["arrays"]["chart"]["dtype"] == "uint8"


def test_frame_metadata_contains_full_visual_reference_result(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "evidence"
    _store(directory).record_frame(_evidence(), (_entry(),))
    reference = _read_json(_frame_directory(directory) / "frame.json")[
        "analysis"
    ]["visual_price_reference_result"]

    assert reference["status"] == "ok"
    assert reference["latest_candidate_x"] == 20
    assert reference["reference"]["anchor_shape"][0]["normalized_high"] == 1.0


def test_candle_trace_preserves_candidate_lifecycle(tmp_path: Path) -> None:
    directory = tmp_path / "evidence"
    _store(directory).record_frame(_evidence(), (_entry(),))
    trace = _read_json(_frame_directory(directory) / "frame.json")["analysis"][
        "candle_detection_trace"
    ]

    assert trace["dominant_width"] == 5.0
    assert "merged" in trace["candidates"][1]["decisions"]
    assert trace["returned_candidate_ids"] == ["c1", "m1"]
    assert trace["series_membership"] is None


def test_frame_metadata_persists_effective_series_membership(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "evidence"
    candle_trace = replace(
        _candle_trace(),
        series_membership=_membership_trace(),
    )
    _store(directory).record_frame(
        _evidence(candle_trace_override=candle_trace),
        (_entry(),),
    )
    membership = _read_json(_frame_directory(directory) / "frame.json")[
        "analysis"
    ]["candle_detection_trace"]["series_membership"]

    assert membership["status"] == "available"
    assert membership["member_candidate_ids"] == ["c1"]
    assert membership["excluded_candidates"] == [
        {
            "candidate_id": "m1",
            "reason": "horizontal_outlier",
            "horizontal_gap_px": 10.0,
            "vertical_gap_px": None,
            "diagnostic": "candidate_isolated_from_supported_lattice",
        }
    ]
    assert membership["estimated_pitch_px"] == 5.0
    assert membership["candidate_runs"][0]["support"] == 1
    assert membership["latest_candidate_id"] == "c1"


def test_latest_and_anchor_roles_use_explicit_candle_coordinates(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "evidence"
    _store(directory).record_frame(_evidence(), (_entry(),))
    trace = _read_json(_frame_directory(directory) / "frame.json")["analysis"][
        "candle_detection_trace"
    ]

    assert trace["latest"]["candidate_id"] == "m1"
    assert trace["latest"]["body_bottom_y"] == 28
    assert trace["anchors"][0]["candidate_id"] == "c1"
    assert trace["anchors"][0]["anchor_index"] == 0
    assert trace["anchors"][0]["high_y"] == 10
    assert trace["anchors"][0]["low_y"] == 39


def test_merge_provenance_is_persisted(tmp_path: Path) -> None:
    directory = tmp_path / "evidence"
    _store(directory).record_frame(_evidence(), (_entry(),))
    trace = _read_json(_frame_directory(directory) / "frame.json")["analysis"][
        "candle_detection_trace"
    ]

    assert trace["merges"][0]["result_candidate_id"] == "m1"
    assert trace["merges"][0]["source_candidate_ids"] == ["s1", "s2"]
    assert trace["candidates"][3]["merged_from"] == ["s1", "s2"]


def test_current_visual_price_extraction_is_persisted(tmp_path: Path) -> None:
    directory = tmp_path / "evidence"
    _store(directory).record_frame(_evidence(), (_entry(),))
    extraction = _read_json(_frame_directory(directory) / "frame.json")[
        "analysis"
    ]["current_visual_price"]

    assert extraction["status"] == "no_visual_price_candidate"
    assert extraction["diagnostic"] == "no_qualifying_rows"


def test_current_visual_price_trace_preserves_no_qualifying_rows(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "evidence"
    _store(directory).record_frame(_evidence(), (_entry(),))
    trace = _read_json(_frame_directory(directory) / "frame.json")["analysis"][
        "current_visual_price_detection_trace"
    ]

    assert trace["effective_chart_right_x"] == 90
    assert trace["effective_chart_right_source"] == "configured"
    assert trace["rejection_counts"]["rows_without_mask_pixels"] == 20
    assert trace["rejection_counts"]["qualifying_rows"] == 0


def test_same_frame_repeat_does_not_reencode(tmp_path: Path) -> None:
    calls = 0

    def encoder(image: np.ndarray) -> bytes:
        nonlocal calls
        calls += 1
        return FilesystemVisualEvidenceRecorder._default_png_encoder(image)

    directory = tmp_path / "evidence"
    store = _store(directory, png_encoder=encoder)
    evidence = _evidence()

    store.record_frame(evidence, (_entry(),))
    store.record_frame(evidence, (_entry(),))

    assert calls == 1


def test_same_association_repeat_does_not_duplicate_manifest(tmp_path: Path) -> None:
    directory = tmp_path / "evidence"
    store = _store(directory)
    evidence = _evidence()
    association = _entry()

    store.record_frame(evidence, (association,))
    store.record_frame(evidence, (association,))

    assert len(_manifest(directory)) == 1


def test_restart_reuses_frame_and_manifest_idempotently(tmp_path: Path) -> None:
    directory = tmp_path / "evidence"
    evidence = _evidence()
    association = _entry()
    _store(directory).record_frame(evidence, (association,))
    calls = 0

    def encoder(image: np.ndarray) -> bytes:
        nonlocal calls
        calls += 1
        return FilesystemVisualEvidenceRecorder._default_png_encoder(image)

    _store(directory, png_encoder=encoder).record_frame(evidence, (association,))

    assert calls == 0
    assert len(_manifest(directory)) == 1


def test_conflicting_frame_pixels_fail_without_overwrite(tmp_path: Path) -> None:
    directory = tmp_path / "evidence"
    store = _store(directory)
    store.record_frame(_evidence(image=_image(seed=1)), (_entry(),))
    original = (_frame_directory(directory) / "chart.png").read_bytes()

    with pytest.raises(ValueError, match="Conflicting evidence"):
        store.record_frame(_evidence(image=_image(seed=2)), (_entry(),))

    assert (_frame_directory(directory) / "chart.png").read_bytes() == original


def test_same_frame_id_with_different_timestamp_fails(tmp_path: Path) -> None:
    directory = tmp_path / "evidence"
    store = _store(directory)
    store.record_frame(_evidence(), (_entry(),))

    with pytest.raises(ValueError, match="same frame_id"):
        store.record_frame(
            _evidence(timestamp=FRAME_TIMESTAMP + timedelta(seconds=1)),
            (_entry(),),
        )


def test_encode_failure_leaves_no_final_frame(tmp_path: Path) -> None:
    def failing_encoder(image: np.ndarray) -> bytes:
        raise ValueError("encode failed")

    directory = tmp_path / "evidence"
    store = _store(directory, png_encoder=failing_encoder)

    with pytest.raises(ValueError, match="encode failed"):
        store.record_frame(_evidence(), (_entry(),))

    assert list((directory / "frames").iterdir()) == []


def test_frame_json_failure_leaves_no_final_frame(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = tmp_path / "evidence"
    store = _store(directory)

    def fail_frame_json(path: Path, payload: dict) -> None:
        raise OSError("frame json failed")

    monkeypatch.setattr(store, "_write_json_file", fail_frame_json)

    with pytest.raises(OSError, match="frame json failed"):
        store.record_frame(_evidence(), (_entry(),))

    assert list((directory / "frames").iterdir()) == []


def test_association_failure_keeps_frame_but_no_partial_pointer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = tmp_path / "evidence"
    store = _store(directory)
    original = store._atomic_write_json

    def fail_entry(path: Path, payload: dict) -> None:
        if path.name == "entry.json":
            raise OSError("association failed")
        original(path, payload)

    monkeypatch.setattr(store, "_atomic_write_json", fail_entry)

    with pytest.raises(OSError, match="association failed"):
        store.record_frame(_evidence(), (_entry(),))

    assert (_frame_directory(directory) / "frame.json").is_file()
    assert list((directory / "snapshots").rglob("entry.json")) == []
    assert _manifest(directory) == []


def test_manifest_append_happens_after_frame_and_association(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = tmp_path / "evidence"
    store = _store(directory)
    original = store._append_manifest
    association = _entry()

    def assert_publication_order(payload: dict) -> None:
        frame_path = directory / "frames" / payload["frame_key"] / "frame.json"
        association_path = (
            directory
            / "snapshots"
            / payload["snapshot_key"]
            / "entry.json"
        )
        assert frame_path.is_file()
        assert association_path.is_file()
        original(payload)

    monkeypatch.setattr(store, "_append_manifest", assert_publication_order)

    store.record_frame(_evidence(), (association,))

    assert len(_manifest(directory)) == 1


def test_persistence_failure_is_recorded_without_traceback(tmp_path: Path) -> None:
    directory = tmp_path / "evidence"
    store = _store(directory, png_encoder=lambda image: b"not-a-png")

    with pytest.raises(ValueError, match="fidelity"):
        store.record_frame(_evidence(), (_entry(),))

    failures = [
        json.loads(line)
        for line in (directory / "failures.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert failures[0]["frame_id"] == 123
    assert failures[0]["stage"] == "publish_frame"
    assert failures[0]["exception_type"] == "ValueError"
    assert "traceback" not in failures[0]


def test_all_persisted_paths_are_relative_to_evidence_root(tmp_path: Path) -> None:
    directory = tmp_path / "absolute-host-path" / "evidence"
    _store(directory).record_frame(_evidence(), (_entry(),))
    frame = _read_json(_frame_directory(directory) / "frame.json")
    association = next((directory / "snapshots").rglob("entry.json"))
    association_payload = _read_json(association)

    assert not Path(frame["images"]["chart"]["filename"]).is_absolute()
    assert not Path(association_payload["frame_metadata_path"]).is_absolute()
    assert str(tmp_path) not in json.dumps(frame)


def test_session_metadata_documents_reproducible_sync_configuration(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "evidence"
    _store(directory)
    metadata = _read_json(directory / "session_metadata.json")

    assert metadata["source_commit"] is None
    assert metadata["application_version"] == "0.1.0-test"
    assert metadata["image_encoding"]["format"] == "png"
    assert metadata["synchronous_persistence"] is True
    assert metadata["evidence_directory"] == "."
    assert metadata["observation_jsonl_path"] == (
        "logs/strategy_observations.jsonl"
    )
    assert "async" in metadata["array_ownership"]


def test_frame_metadata_contains_honest_timing_and_size_metrics(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "evidence"
    _store(directory).record_frame(_evidence(), (_entry(),))
    frame = _read_json(_frame_directory(directory) / "frame.json")
    manifest = _manifest(directory)[0]

    assert frame["persistence"]["image_encode_write_duration_ms"] >= 0
    assert manifest["record_frame_duration_ms_before_manifest_append"] >= 0
    assert manifest["png_bytes_written"] > 0


def test_no_price_observation_image_creates_only_chart_role(tmp_path: Path) -> None:
    directory = tmp_path / "evidence"
    _store(directory).record_frame(_evidence(price_image=None), (_entry(),))
    frame_directory = _frame_directory(directory)
    metadata = _read_json(frame_directory / "frame.json")

    assert metadata["images"]["price_observation"] is None
    assert sorted(path.name for path in frame_directory.glob("*.png")) == [
        "chart.png"
    ]


def test_same_snapshot_phase_cannot_point_to_different_frame(tmp_path: Path) -> None:
    directory = tmp_path / "evidence"
    store = _store(directory)
    association = _entry()
    store.record_frame(_evidence(frame_id=123), (association,))

    with pytest.raises(ValueError, match="Conflicting evidence association"):
        store.record_frame(
            _evidence(
                frame_id=124,
                timestamp=FRAME_TIMESTAMP + timedelta(seconds=1),
            ),
            (association,),
        )


def test_corrupt_existing_manifest_is_rejected_conservatively(tmp_path: Path) -> None:
    directory = tmp_path / "evidence"
    _store(directory)
    (directory / "manifest.jsonl").write_text("{broken\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid manifest JSON"):
        _store(directory)


def test_public_filesystem_contracts_resolve_runtime_type_hints() -> None:
    assert isinstance(_store, object)
    assert get_type_hints(FilesystemVisualEvidenceRecorder.__init__)
    assert get_type_hints(FilesystemVisualEvidenceRecorder.record_frame)
    assert get_type_hints(FilesystemVisualEvidenceRecorder.frame_key)
    assert get_type_hints(FilesystemVisualEvidenceRecorder.snapshot_key)
    assert get_type_hints(VisualEvidenceSerializer.analysis_to_dict)
    assert get_type_hints(VisualEvidenceRecorder.record_frame)
