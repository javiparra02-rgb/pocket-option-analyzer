"""Synthetic images only. No real capture, GUI, CVP extraction or replay."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from time import perf_counter

import cv2
import numpy as np
import pytest
from test_accepted_signal_evidence import IMAGE, analyze, at, enable, setup

from pocket_option_analyzer.application.evidence.observational_evidence import (
    ObservationalEvidenceConfig,
    ObservationalEvidenceRecorder,
)
from pocket_option_analyzer.application.signals.accepted_signal_evidence import (
    AcceptedSignalEvidenceRecorder,
)
from pocket_option_analyzer.infrastructure.bootstrap.signal_pipeline_factory import (
    SignalPipelineFactory,
)
from pocket_option_analyzer.infrastructure.config import Settings
from pocket_option_analyzer.infrastructure.evidence.observational_evidence_writer import (  # noqa: E501
    ObservationalEvidenceWriter,
)


def config(tmp_path, **changes):
    # Test-only budgets: 20x20x3=1200 bytes/frame, four retained opportunities;
    # enough metadata headroom, not production defaults or a promised FPS.
    return replace(
        ObservationalEvidenceConfig(
            directory=tmp_path / "originals",
            max_frame_bytes=4096,
            max_retained_bytes=16384,
            max_pending_acceptances=4,
            max_queue_items=8,
            max_queue_bytes=65536,
            max_storage_bytes=1048576,
            pending_retention_seconds=60,
        ),
        **changes,
    )


def experiment(tmp_path, direction="call", **changes):
    cfg = config(tmp_path, **changes)
    writer = ObservationalEvidenceWriter(cfg, background=False)
    test = setup(direction)
    test.originals = ObservationalEvidenceRecorder(cfg, writer)
    test.pipeline.observational_evidence = test.originals
    test.original_writer = writer
    return test


def package(test, identity=None):
    test.original_writer.drain()
    identity = identity or test.pipeline.accepted_evidence.last_accepted.acceptance_id
    return json.loads(test.original_writer.package_path(identity).read_text("utf-8"))


def events(test):
    return [
        json.loads(line)
        for line in (test.original_writer.directory / "events.jsonl")
        .read_text()
        .splitlines()
    ]


def role_pixels(test, manifest, role, image="chart"):
    descriptor = manifest["roles"][role]["images"][image]
    path = test.original_writer.directory / descriptor["path"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == descriptor["sha256"]
    return cv2.imread(str(path), cv2.IMREAD_UNCHANGED)


@pytest.mark.parametrize("direction", ["call", "put"])
def test_neutral_then_acceptance_preserves_own_frame_and_single_evaluation(
    tmp_path, direction
):
    test = experiment(tmp_path, direction)
    analyze(test, 2, 1)
    enable(test)
    original = np.full_like(IMAGE, 37)
    test.pipeline.analyze_and_record(original, created_at=at(5), frame_id=2)
    original[:] = 99
    manifest = package(test)
    assert manifest["acceptance_id"] == test.signals.events[0]["acceptance_id"]
    assert manifest["roles"]["ENTRY"]["frame"]["frame_id"] == 2
    assert np.all(role_pixels(test, manifest, "ENTRY") == 37)
    assert test.evaluator.calls == test.indicators.calls == 2
    assert len(test.signals.events) == 1
    assert manifest["package_state"] == "PACKAGE_PARTIAL"


def test_copy_precedes_analysis_mutation(tmp_path, monkeypatch):
    test = experiment(tmp_path)
    enable(test)
    original_analyze = test.pipeline._analysis_pipeline.analyze

    def mutate(**kwargs):
        kwargs["image"][:] = 77
        return original_analyze(**kwargs)

    monkeypatch.setattr(test.pipeline._analysis_pipeline, "analyze", mutate)
    image = np.full_like(IMAGE, 11)
    test.pipeline.analyze_and_record(image, created_at=at(2), frame_id=1)
    assert np.all(role_pixels(test, package(test), "ENTRY") == 11)


def test_pre_and_exit_are_exact_sq03_selection_with_lateness(tmp_path):
    test = experiment(tmp_path)
    enable(test)
    analyze(test, 2, 1)
    analyze(test, 9, 2)
    analyze(test, 11, 3)
    analyze(test, 14.5, 4)
    selected = test.pipeline.accepted_evidence.last_exit
    analyze(test, 15, 5)
    manifest = package(test)
    assert manifest["roles"]["PRE_EXPIRY"]["frame"]["frame_id"] == 3
    assert manifest["roles"]["SQ03_EXIT"]["frame"]["frame_id"] == 4
    assert selected.to_dict()["exit_evaluation"]["frame_id"] == 4
    assert selected.to_dict()["lateness_seconds"] == 2.5
    assert manifest["package_state"] == "PACKAGE_COMPLETE"
    assert manifest["instrument_identity"] == "UNKNOWN"
    assert not manifest["nominal_outcome_verified"]
    assert "outcome" not in manifest
    assert test.originals.pending_count == test.originals.retained_bytes == 0


def test_two_acceptances_same_snapshot_have_separate_associations(tmp_path):
    test = experiment(tmp_path)
    enable(test)
    analyze(test, 2, 1)
    first = test.pipeline.accepted_evidence.last_accepted
    # Use a second fresh gate only to create an independent synthetic acceptance;
    # real production gate behavior is neither changed nor bypassed.
    other = experiment(tmp_path / "other")
    enable(other)
    analyze(other, 3, 2)
    second = other.pipeline.accepted_evidence.last_accepted
    assert (
        first.to_dict()["evaluation"]["snapshot_id"]
        == second.to_dict()["evaluation"]["snapshot_id"]
    )
    frame = other.originals._pending[second.acceptance_id].entry
    test.originals.accepted(second, frame)
    left = package(test, first.acceptance_id)
    right = package(test, second.acceptance_id)
    assert left["acceptance_id"] != right["acceptance_id"]
    assert left["roles"]["ENTRY"]["images"] == right["roles"]["ENTRY"]["images"]
    assert (
        left["roles"]["ENTRY"]["logical_identity"]
        != right["roles"]["ENTRY"]["logical_identity"]
    )


def test_sq03_reports_all_selected_exits_not_just_last(tmp_path):
    test = experiment(tmp_path)
    enable(test)
    analyze(test, 2)
    first = test.pipeline.accepted_evidence.last_accepted
    native = test.pipeline.accepted_evidence
    # Second ordinal/acceptance for controlled recorder-level composition.
    evaluation = native.capture(at(3), first.evaluation.to_dict())
    native.accept(evaluation, test.signals.attempts[0][0], at(3), memory_only=True)
    selected = native.observe_exits(native.capture(at(15), first.evaluation.to_dict()))
    assert len(selected) == 2
    assert len({item.acceptance_id for item in selected}) == 2


def test_session_stop_records_missing_exit_without_fabricating_one(tmp_path):
    test = experiment(tmp_path)
    enable(test)
    analyze(test, 2)
    test.originals.stop_session()
    manifest = package(test)
    assert manifest["roles"]["SQ03_EXIT"]["state"] == "SQ03_EXIT_MISSING"
    assert manifest["closed"]
    assert manifest["package_state"] == "PACKAGE_PARTIAL"


def test_signal_writer_error_is_still_raised_after_acceptance_known(tmp_path):
    test = experiment(tmp_path)
    enable(test)
    test.signals.fail = True
    with pytest.raises(OSError, match="signal write failed"):
        analyze(test, 2)
    assert not test.pipeline.accepted_evidence.last_accepted_persisted
    assert package(test)["roles"]["ENTRY"]["state"] == "WRITE_CONFIRMED"
    assert any(
        e["event"] == "SQ03_SIGNAL_WRITE" and e["state"] == "WRITE_FAILED"
        for e in events(test)
    )
    test.signals.fail = False
    identity = test.pipeline.accepted_evidence.last_accepted.acceptance_id
    test.pipeline.retry_accepted_evidence(identity)
    assert analyze(test, 3).is_duplicate_suppressed
    assert test.evaluator.calls == 2


@pytest.mark.parametrize("failure", ["png", "manifest"])
def test_write_failures_are_not_reported_as_complete(tmp_path, monkeypatch, failure):
    test = experiment(tmp_path)
    enable(test)

    def fail(*args, **kwargs):
        raise OSError("injected disk failure")

    monkeypatch.setattr(
        test.original_writer, "_image" if failure == "png" else "_atomic_manifest", fail
    )
    analyze(test, 2)
    test.original_writer.drain()
    assert test.original_writer.failure_count > 0
    identity = test.pipeline.accepted_evidence.last_accepted.acceptance_id
    path = test.original_writer.package_path(identity)
    if failure == "png":
        assert json.loads(path.read_text())["roles"]["ENTRY"]["state"] == "WRITE_FAILED"
    else:
        assert not path.exists()
        assert any(e["event"] == "WRITE_FAILED" for e in events(test))


@pytest.mark.parametrize("limit", ["max_queue_items", "max_queue_bytes"])
def test_queue_limits_document_loss_and_do_not_change_gate(tmp_path, limit):
    changes = {limit: 1}
    test = experiment(tmp_path, **changes)
    enable(test)
    first = analyze(test, 2)
    assert first.is_actionable
    analyze(test, 13)
    assert test.original_writer.queued_items <= test.originals.config.max_queue_items
    assert test.original_writer.queued_bytes <= test.originals.config.max_queue_bytes
    assert any(e.get("reason") == "QUEUE_LIMIT" for e in events(test))


def test_retention_and_candidate_limits_are_enforced(tmp_path):
    test = experiment(tmp_path, max_frame_bytes=32)
    enable(test)
    analyze(test, 2)
    manifest = package(test)
    assert manifest["roles"]["ENTRY"]["state"] == "ENTRY_MISSING"
    assert manifest["roles"]["ENTRY"]["reason"] == "FRAME_BYTE_LIMIT"
    assert test.originals.retained_bytes == 0


def test_pending_count_and_retained_bytes_are_bounded(tmp_path):
    test = experiment(tmp_path, max_pending_acceptances=1)
    enable(test)
    analyze(test, 2)
    other = experiment(tmp_path / "second")
    enable(other)
    analyze(other, 3)
    extra = other.pipeline.accepted_evidence.last_accepted
    test.originals.accepted(extra, other.originals._pending[extra.acceptance_id].entry)
    assert test.originals.pending_count == 1
    assert test.originals.retained_bytes <= test.originals.config.max_retained_bytes
    assert any(e.get("reason") == "RETENTION_LIMIT" for e in events(test))


def test_retention_expiry_is_operational_not_outcome(tmp_path):
    test = experiment(tmp_path, pending_retention_seconds=1)
    now = [0.0]
    test.originals._clock = lambda: now[0]
    enable(test)
    analyze(test, 2)
    now[0] = 2.0
    analyze(test, 3)
    manifest = package(test)
    assert manifest["roles"]["SQ03_EXIT"]["reason"] == "RETENTION_EXPIRED"
    assert test.originals.pending_count == 0


def test_restart_marks_incomplete_package_and_does_not_select_exit(tmp_path):
    test = experiment(tmp_path)
    enable(test)
    analyze(test, 2)
    before = package(test)
    recovered = ObservationalEvidenceWriter(test.originals.config, background=False)
    identity = before["acceptance_id"]
    after = json.loads(recovered.package_path(identity).read_text())
    assert after["closed"]
    assert "RESTART_BEFORE_COMPLETION" in after["failures"]
    assert after["roles"]["SQ03_EXIT"]["reason"] == "RESTART"
    assert after["roles"]["ENTRY"] == before["roles"]["ENTRY"]


def test_duplicate_acceptance_does_not_replace_original(tmp_path):
    test = experiment(tmp_path)
    enable(test)
    analyze(test, 2)
    evidence = test.pipeline.accepted_evidence.last_accepted
    pending = test.originals._pending[evidence.acceptance_id]
    test.originals.accepted(evidence, pending.entry)
    assert test.original_writer.queued_items == 1
    assert any(e["event"] == "DUPLICATE_ACCEPTANCE" for e in events(test))


def test_clock_regression_is_recorded_not_normalized(tmp_path):
    test = experiment(tmp_path)
    enable(test)
    analyze(test, 5)
    analyze(test, 4)
    assert any(e["event"] == "WALL_CLOCK_REGRESSION" for e in events(test))
    assert test.pipeline.accepted_evidence.last_accepted.resolve_at == at(15)


def test_incompatible_retry_preserves_confirmed_frame(tmp_path):
    test = experiment(tmp_path)
    enable(test)
    analyze(test, 2)
    original = package(test)
    evidence = test.pipeline.accepted_evidence.last_accepted
    owned = test.originals._pending[evidence.acceptance_id].entry
    changed = test.originals.capture(
        np.full_like(IMAGE, 77), None, None, json.loads(owned.metadata_json)
    )
    test.original_writer.submit(evidence.to_dict(), {"ENTRY": changed}, closed=False)
    after = package(test)
    assert after["roles"]["ENTRY"] == original["roles"]["ENTRY"]
    assert test.original_writer.failure_count > 0


def test_storage_quota_failure_is_explicit(tmp_path):
    test = experiment(tmp_path, max_storage_bytes=1)
    enable(test)
    analyze(test, 2)
    test.original_writer.drain()
    assert test.original_writer.failure_count > 0
    assert test.original_writer.lost_event_count > 0
    assert not test.original_writer.package_path(
        test.pipeline.accepted_evidence.last_accepted.acceptance_id
    ).exists()


def test_opt_in_is_disabled_and_no_directory_is_created(tmp_path):
    settings = Settings(_env_file=None)
    assert settings.observational_evidence_enabled is False
    pipeline = SignalPipelineFactory.create_visual_signal_recording_pipeline()
    assert pipeline.observational_evidence is None
    assert not (tmp_path / "originals").exists()


def test_directory_inside_repository_is_rejected(tmp_path):
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    with pytest.raises(ValueError, match="outside the repository"):
        ObservationalEvidenceWriter(
            config(tmp_path, directory=root / "logs" / "forbidden")
        )
    assert not (root / "logs" / "forbidden").exists()


@pytest.mark.parametrize(
    "field",
    [
        "max_queue_items",
        "max_frame_bytes",
        "max_storage_bytes",
        "pending_retention_seconds",
    ],
)
def test_budgets_are_explicit_positive_values(tmp_path, field):
    with pytest.raises(ValueError):
        config(tmp_path, **{field: 0})


def test_background_writer_flush_and_cost_are_observable(tmp_path):
    cfg = config(tmp_path)
    writer = ObservationalEvidenceWriter(cfg)
    test = setup()
    test.pipeline.observational_evidence = ObservationalEvidenceRecorder(cfg, writer)
    enable(test)
    started = perf_counter()
    analyze(test, 2)
    analyze(test, 13)
    assert writer.flush(timeout=5)
    assert writer.queued_items == writer.queued_bytes == 0
    assert writer.last_write_seconds is not None
    assert writer.last_write_seconds >= 0
    assert perf_counter() >= started  # no machine-dependent timing threshold


def test_unknown_instrument_and_no_automatic_outcome(tmp_path):
    test = experiment(tmp_path)
    enable(test)
    analyze(test, 2)
    manifest = package(test)
    frame = manifest["roles"]["ENTRY"]["frame"]
    assert frame["instrument_identity"] == "UNKNOWN"
    assert frame["quote_effective_at"] is None
    assert frame["nominal_outcome_authorized"] is False
    assert "instrument_context" not in manifest["roles"]["ENTRY"]["images"]


def test_namespace_is_native_sq03_not_new_experimental_identity(tmp_path):
    test = experiment(tmp_path)
    enable(test)
    analyze(test, 2)
    accepted = test.pipeline.accepted_evidence.last_accepted
    manifest = package(test)
    assert (
        manifest["acceptance"]["evaluation"]["execution_id"]
        == accepted.evaluation.execution_id
    )
    assert (
        manifest["acceptance"]["evaluation"]["evaluation_id"]
        == accepted.evaluation.evaluation_id
    )
    assert (
        AcceptedSignalEvidenceRecorder().execution_id
        != accepted.evaluation.execution_id
    )


def test_pre_retained_byte_limit_records_missing_not_an_older_substitute(tmp_path):
    test = experiment(tmp_path, max_retained_bytes=4096)
    enable(test)
    for second in (2, 9, 13):
        test.pipeline.analyze_and_record(
            np.zeros((32, 32, 3), dtype=np.uint8),
            created_at=at(second),
            frame_id=second,
        )
    manifest = package(test)
    assert manifest["roles"]["PRE_EXPIRY"]["state"] == "PRE_EXPIRY_MISSING"
    assert any(event.get("reason") == "PRE_BYTE_LIMIT" for event in events(test))
    assert test.originals.retained_bytes <= 4096


def test_recovery_does_not_trust_complete_manifest_with_missing_png(tmp_path):
    test = experiment(tmp_path)
    enable(test)
    analyze(test, 2)
    analyze(test, 13)
    manifest = package(test)
    assert manifest["package_state"] == "PACKAGE_COMPLETE"
    png = (
        test.original_writer.directory
        / manifest["roles"]["ENTRY"]["images"]["chart"]["path"]
    )
    png.unlink()  # synthetic fixture only
    recovered = ObservationalEvidenceWriter(test.originals.config, background=False)
    restored = json.loads(recovered.package_path(manifest["acceptance_id"]).read_text())
    assert restored["package_state"] == "PACKAGE_PARTIAL"
    assert "RECOVERY_INTEGRITY_FAILURE" in restored["failures"]


def test_naive_time_does_not_create_fake_sq03_exit(tmp_path):
    test = experiment(tmp_path)
    # The legacy observation model rejects naive timestamps; isolate the
    # existing permissive signal path without changing that legacy contract.
    test.pipeline._observation_recorder = None
    enable(test)
    test.pipeline.analyze_and_record(
        IMAGE, created_at=at(2).replace(tzinfo=None), frame_id=1
    )
    test.pipeline.analyze_and_record(
        IMAGE, created_at=at(13).replace(tzinfo=None), frame_id=2
    )
    test.originals.stop_session()
    manifest = package(test)
    assert manifest["roles"]["SQ03_EXIT"]["state"] == "SQ03_EXIT_MISSING"


def test_originals_do_not_change_strict_or_gate_dispositions(tmp_path):
    baseline = setup()
    enabled = experiment(tmp_path)
    for seconds in (2, 3, 11, 14, 32, 33):
        if seconds == 3:
            enable(baseline)
            enable(enabled)
        left = analyze(baseline, seconds)
        right = analyze(enabled, seconds)
        assert left.signal.direction == right.signal.direction
        assert left.disposition == right.disposition
        assert left.candle_interval_started_at == right.candle_interval_started_at
    assert baseline.evaluator.calls == enabled.evaluator.calls == 6


def test_same_original_is_idempotent_on_write_retry(tmp_path):
    test = experiment(tmp_path)
    enable(test)
    analyze(test, 2)
    before = package(test)
    evidence = test.pipeline.accepted_evidence.last_accepted
    frame = test.originals._pending[evidence.acceptance_id].entry
    test.original_writer.submit(evidence.to_dict(), {"ENTRY": frame}, closed=False)
    after = package(test)
    assert after["roles"]["ENTRY"] == before["roles"]["ENTRY"]
    assert len(list((test.original_writer.directory / "objects").glob("*.png"))) == 1


def test_write_failure_never_changes_selected_exit_frame(tmp_path, monkeypatch):
    test = experiment(tmp_path)
    enable(test)
    analyze(test, 2)
    test.original_writer.drain()
    actual_image = test.original_writer._image

    def fail(image):
        raise OSError("temporary PNG failure")

    monkeypatch.setattr(test.original_writer, "_image", fail)
    analyze(test, 13, 2)
    before = package(test)
    assert before["roles"]["SQ03_EXIT"]["frame"]["frame_id"] == 2
    analyze(test, 14, 3)
    monkeypatch.setattr(test.original_writer, "_image", actual_image)
    assert test.original_writer.retry_failed(before["acceptance_id"]) == 1
    after = package(test)
    assert after["roles"]["SQ03_EXIT"]["frame"]["frame_id"] == 2
    assert after["package_state"] == "PACKAGE_COMPLETE"


def test_factory_enables_experiment_only_with_explicit_config(tmp_path):
    cfg = config(tmp_path)
    pipeline = SignalPipelineFactory.create_visual_signal_recording_pipeline(
        observational_evidence_config=cfg
    )
    assert pipeline.observational_evidence is not None
    assert pipeline.observational_evidence.config == cfg


def test_restart_documents_known_acceptance_even_without_manifest(tmp_path):
    test = experiment(tmp_path)
    enable(test)
    analyze(test, 2)
    assert test.original_writer.queued_items == 1  # Simulated interruption before write
    ObservationalEvidenceWriter(test.originals.config, background=False)
    assert any(e["event"] == "RESTART_UNPUBLISHED_ACCEPTANCE" for e in events(test))


def test_manifest_digest_and_originals_are_independently_checked(tmp_path):
    test = experiment(tmp_path)
    enable(test)
    analyze(test, 2)
    manifest = package(test)
    identity = manifest["acceptance_id"]
    digest = manifest.pop("manifest_sha256")
    canonical = json.dumps(
        manifest,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    assert hashlib.sha256(canonical).hexdigest() == digest
    assert test.original_writer.read_package(identity)["acceptance_id"] == identity
    path = (
        test.original_writer.directory
        / manifest["roles"]["ENTRY"]["images"]["chart"]["path"]
    )
    path.write_bytes(b"synthetic corruption")
    with pytest.raises(ValueError, match="ORIGINAL_INTEGRITY_FAILURE"):
        test.original_writer.read_package(identity)


def test_failed_retries_share_queue_budget_and_explicit_discard_is_logged(
    tmp_path, monkeypatch
):
    test = experiment(tmp_path)
    enable(test)

    def fail(image):
        raise OSError("synthetic failure")

    monkeypatch.setattr(test.original_writer, "_image", fail)
    analyze(test, 2)
    test.original_writer.drain()
    assert test.original_writer.queued_items == 1
    assert test.original_writer.queued_bytes <= test.originals.config.max_queue_bytes
    test.original_writer.discard_failed()
    assert test.original_writer.queued_items == test.original_writer.queued_bytes == 0
    assert any(
        e.get("reason") == "RETAINED_RETRY_EXPLICITLY_DISCARDED" for e in events(test)
    )


def test_wrong_evaluation_frame_is_not_attached_to_acceptance(tmp_path):
    test = experiment(tmp_path)
    enable(test)
    analyze(test, 2)
    first = test.pipeline.accepted_evidence.last_accepted
    other = experiment(tmp_path / "other")
    enable(other)
    analyze(other, 3)
    test.originals.accepted(
        other.pipeline.accepted_evidence.last_accepted,
        test.originals._pending[first.acceptance_id].entry,
    )
    manifest = package(
        test, other.pipeline.accepted_evidence.last_accepted.acceptance_id
    )
    assert manifest["roles"]["ENTRY"]["reason"] == "FRAME_IDENTITY_MISMATCH"


def test_blocked_png_worker_does_not_wait_for_png_before_next_decision(
    tmp_path, monkeypatch
):
    from threading import Event, Thread

    cfg = config(tmp_path, max_queue_items=1)
    writer = ObservationalEvidenceWriter(cfg)
    started, release, finished = Event(), Event(), Event()
    encode = writer._image

    def blocked(image):
        started.set()
        assert release.wait(timeout=5)  # Test synchronization, not production tolerance
        return encode(image)

    monkeypatch.setattr(writer, "_image", blocked)
    test = setup()
    test.pipeline.observational_evidence = ObservationalEvidenceRecorder(cfg, writer)
    enable(test)
    analyze(test, 2)
    assert started.wait(timeout=5)
    results = []

    def next_frame():
        results.append(analyze(test, 13))
        finished.set()

    worker = Thread(target=next_frame)
    worker.start()
    try:
        assert finished.wait(timeout=5)
        assert results[0].is_duplicate_suppressed
        assert not release.is_set()
    finally:
        release.set()
        worker.join(timeout=5)
    assert writer.flush(timeout=5)


def test_disabled_runtime_ignores_config_without_creating_storage(tmp_path):
    from types import SimpleNamespace

    from pocket_option_analyzer.infrastructure.bootstrap import (
        PocketOptionRuntimeFactory,
    )

    cfg = config(tmp_path)
    settings = Settings(
        _env_file=None,
        observational_evidence_enabled=False,
        observational_evidence_config=cfg,
    )
    PocketOptionRuntimeFactory.create_runtime_service(
        capture_service=SimpleNamespace(capture_once=lambda: None),
        settings=settings,
        signal_file_path=None,
        observation_file_path=None,
    )
    assert not cfg.directory.exists()


@pytest.mark.parametrize("shape", [(720, 1280, 4), (1080, 1920, 3)])
def test_synthetic_large_original_roundtrip_cost(tmp_path, shape):
    image = np.random.default_rng(2026).integers(0, 256, shape, dtype=np.uint8)
    size = image.nbytes
    # Derived from this fixture, not a claimed production memory/FPS default.
    cfg = config(
        tmp_path,
        max_frame_bytes=size,
        max_retained_bytes=2 * size,
        max_queue_bytes=8 * size,
        max_storage_bytes=12 * size,
    )
    writer = ObservationalEvidenceWriter(cfg)
    test = setup()
    test.pipeline.observational_evidence = ObservationalEvidenceRecorder(cfg, writer)
    enable(test)
    started = perf_counter()
    for second in (2, 13):
        test.pipeline.analyze_and_record(image, created_at=at(second), frame_id=second)
    submitted = perf_counter()
    assert writer.flush(timeout=30)
    completed = perf_counter()
    identity = test.pipeline.accepted_evidence.last_accepted.acceptance_id
    manifest = writer.read_package(identity)
    assert manifest["package_state"] == "PACKAGE_COMPLETE"
    descriptor = manifest["roles"]["ENTRY"]["images"]["chart"]
    saved = cv2.imread(str(writer.directory / descriptor["path"]), cv2.IMREAD_UNCHANGED)
    assert np.array_equal(saved, image)
    assert writer.queued_bytes == writer.queued_items == 0
    print(
        f"synthetic={shape} raw_bytes={size} "
        f"producer_ms={(submitted - started) * 1000:.2f} "
        f"total_ms={(completed - started) * 1000:.2f}"
    )
