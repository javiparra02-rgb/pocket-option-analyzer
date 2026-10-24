from __future__ import annotations

import json
import os
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from sq04c_harness.composition import SyntheticSource, build_synthetic
from sq04c_harness.config import HarnessConfig
from sq04c_harness.isolation import (
    COMMIT,
    PROTECTED,
    IsolationError,
    git,
    outside,
    prepare_snapshot,
    product_origins,
    repository_state,
    require_baseline,
    safe_relative,
    sha256,
    verify_snapshot,
)


def test_explicit_config_and_unchanged_product_default(config: HarnessConfig) -> None:
    assert config.validate().max_frame_bytes == 8 * 1024**2
    from pocket_option_analyzer.infrastructure.config import Settings

    assert Settings.model_fields["observational_evidence_enabled"].default is False


@pytest.mark.parametrize(
    "field", ["max_frame_bytes", "context_region", "max_queue_items"]
)
def test_incomplete_configuration(config: HarnessConfig, field: str) -> None:
    budgets = dict(config.budgets)
    del budgets[field]
    with pytest.raises(ValueError, match="Complete explicit"):
        replace(config, budgets=budgets).validate()


@pytest.mark.parametrize(
    "changes",
    [
        {"capture_observational": False},
        {"pipeline_observational": False},
        {"mode": "OFF"},
        {"mode": "ON"},
        {"mode": "LIVE"},
        {"flush_timeout": float("nan")},
        {"max_cycles": 0},
        {"max_cycles": 100},
        {"capture_observational": 1},
    ],
)
def test_reject_inconsistent_or_real(
    config: HarnessConfig, changes: dict[str, Any]
) -> None:
    with pytest.raises(ValueError):
        replace(config, **changes).validate()


def test_synthetic_source_cannot_accept_capture_adapter() -> None:
    with pytest.raises(TypeError):
        SyntheticSource(lambda: pytest.fail("live capture"))  # type: ignore[call-arg]
    source = SyntheticSource()
    frame = source.capture_once()
    assert frame.source_key == "SYNTHETIC_NO_SCREEN"
    assert frame.image.shape == (64, 64, 3)
    assert not frame.image.any()


@pytest.mark.parametrize(
    "name",
    [
        "../escape",
        "/absolute",
        "a\\b",
        "C:/escape",
        "a//b",
        "a/NUL.txt",
        "a/name.",
        "a/name ",
        ".git/config",
        "a:stream",
        "a/./b",
    ],
)
def test_unsafe_snapshot_paths(name: str) -> None:
    with pytest.raises(IsolationError):
        safe_relative(name)


def test_output_protects_repository_and_snapshot(config: HarnessConfig) -> None:
    for root in (config.repository, config.snapshot):
        with pytest.raises(IsolationError):
            outside(root / "evidence", config.repository, config.snapshot)
    with pytest.raises(IsolationError):
        prepare_snapshot(config.repository, config.repository / "do-not-create")
    assert not (config.repository / "do-not-create").exists()


def test_committed_snapshot_identity_and_dirty_h3_exclusion(
    config: HarnessConfig,
) -> None:
    run = Path(os.environ["SQ04C_RUN"])
    manifest = json.loads((run / "snapshot_identity.json").read_text("utf-8"))
    verify_snapshot(config.snapshot, manifest)
    assert manifest["commit"] == COMMIT
    assert (config.snapshot / "pyproject.toml").read_bytes() == git(
        config.repository,
        "cat-file",
        "blob",
        f"{COMMIT}:pyproject.toml",
    )
    for name, dirty_hash in PROTECTED.items():
        assert sha256(config.repository / name) == dirty_hash
        assert (config.snapshot / name).read_bytes() == git(
            config.repository,
            "cat-file",
            "blob",
            f"{COMMIT}:{name}",
        )
        assert sha256(config.snapshot / name) != dirty_hash


def test_adulterated_snapshot_rejected(tmp_path: Path) -> None:
    from hashlib import sha256 as digest

    root = tmp_path / "tiny-snapshot"
    root.mkdir()
    original = b"original\r\n"
    (root / "module.py").write_bytes(original)
    manifest = {
        "commit": COMMIT,
        "blobs": [{"path": "module.py", "sha256": digest(original).hexdigest()}],
    }
    verify_snapshot(root, manifest)
    (root / "module.py").write_bytes(b"original\n")
    with pytest.raises(IsolationError):
        verify_snapshot(root, manifest)


def test_product_imports_confined(config: HarnessConfig) -> None:
    from pocket_option_analyzer.infrastructure.bootstrap import SignalPipelineFactory

    assert SignalPipelineFactory is not None
    origins = product_origins(config.snapshot)
    assert origins
    assert all(
        Path(p).is_relative_to(config.snapshot / "src") for p in origins.values()
    )
    assert sys.dont_write_bytecode


def test_namespace_package_is_confined(config: HarnessConfig) -> None:
    import pocket_option_analyzer.infrastructure as namespace

    assert namespace.__file__ is None
    assert all(
        Path(p).is_relative_to(config.snapshot / "src") for p in namespace.__path__
    )


def test_reject_loaded_product_outside_snapshot(
    config: HarnessConfig,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import ModuleType

    injected = ModuleType("pocket_option_analyzer.synthetic_escape_test")
    injected.__file__ = str(tmp_path / "outside.py")
    with monkeypatch.context() as context:
        context.setitem(sys.modules, injected.__name__, injected)
        with pytest.raises(IsolationError, match="escaped snapshot"):
            product_origins(config.snapshot)


@pytest.mark.parametrize("stage", ["loaded", "prospective"])
def test_s9_namespace_with_mixed_origins_rejected(
    config: HarnessConfig,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stage: str,
) -> None:
    from importlib.machinery import ModuleSpec, PathFinder
    from types import ModuleType

    from sq04c_harness.isolation import ProductImportGuard

    name = "pocket_option_analyzer.synthetic_mixed_namespace"
    locations = [str(config.snapshot / "src" / "pocket_option_analyzer"), str(tmp_path)]
    with monkeypatch.context() as context:
        if stage == "loaded":
            namespace = ModuleType(name)
            namespace.__path__ = locations
            context.setitem(sys.modules, name, namespace)
            with pytest.raises(IsolationError, match="escaped snapshot"):
                product_origins(config.snapshot)
        else:
            spec = ModuleSpec(name, loader=None, is_package=True)
            spec.submodule_search_locations = locations
            context.setattr(PathFinder, "find_spec", lambda *args: spec)
            with pytest.raises(IsolationError, match="escaped snapshot"):
                ProductImportGuard(config.snapshot).find_spec(name)


@pytest.mark.parametrize(
    "entries",
    [
        b"120000 blob " + b"a" * 40 + b"\tlink\0",
        b"160000 commit " + b"a" * 40 + b"\tsubmodule\0",
        b"100644 blob "
        + b"a" * 40
        + b"\tA.py\0"
        + b"100644 blob "
        + b"b" * 40
        + b"\ta.py\0",
        b"100644 blob "
        + b"a" * 40
        + b"\ta\0"
        + b"100644 blob "
        + b"b" * 40
        + b"\ta/b\0",
    ],
)
def test_tree_rejects_unsupported_or_ambiguous_entries(
    config: HarnessConfig,
    monkeypatch: pytest.MonkeyPatch,
    entries: bytes,
) -> None:
    from sq04c_harness import isolation

    monkeypatch.setattr(isolation, "git", lambda *args: entries)
    with pytest.raises(IsolationError):
        isolation.tree_entries(config.repository)


def test_original_repository_protected(config: HarnessConfig) -> None:
    state = repository_state(config.repository)
    require_baseline(state)
    before = json.loads(
        (Path(os.environ["SQ04C_RUN"]) / "repository_before.json").read_text()
    )
    assert before == state


def test_driver_returns_failure_if_post_pytest_snapshot_verification_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    from sq04c_harness import validate as driver

    monkeypatch.setattr(
        driver, "repository_state", lambda repository: {"fake": "stable"}
    )
    monkeypatch.setattr(driver, "require_baseline", lambda state: None)
    monkeypatch.setattr(driver, "prepare_snapshot", lambda *args: {"fake": "snapshot"})
    monkeypatch.setattr(
        driver.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=0)
    )

    def reject_snapshot(*args: Any) -> None:
        raise IsolationError("synthetic post-pytest integrity failure")

    monkeypatch.setattr(driver, "verify_snapshot", reject_snapshot)
    status, run = driver.validate(
        tmp_path / "fake-repository", tmp_path / "driver-output"
    )
    report = json.loads((run / "results" / "validation.json").read_text("utf-8"))
    assert status != 0
    assert report["verdict"] == "SQ04C_S8_ISOLATION_FAILED"
    assert report["original_repository_unchanged"]


@pytest.mark.parametrize("enabled", [False, True])
def test_real_public_composition_on_synthetic_pixels_only(
    config: HarnessConfig,
    enabled: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pocket_option_analyzer.infrastructure.bootstrap import (
        PocketOptionRuntimeFactory,
    )

    def forbidden_capture(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("Real capture factory must never be used")

    # Test-only fail-fast spy; production control never patches product objects.
    monkeypatch.setattr(
        PocketOptionRuntimeFactory, "create_capture_service", forbidden_capture
    )
    config = replace(
        config, capture_observational=enabled, pipeline_observational=enabled
    )
    supervisor = build_synthetic(config)
    supervisor.start()
    assert supervisor.done.wait(5)
    report = supervisor.close(join_timeout=5, flush_timeout=5)
    assert report["state"] == "CLOSED_VERIFIED", report
    assert report["metrics"]["cycles"] == 3
    assert report["metrics"]["evaluations"] == 3
    assert not report["live_capture_performed"]
    assert supervisor.pipeline.observational_evidence is supervisor.recorder
    if enabled:
        assert supervisor.recorder.writer is supervisor.writer
    else:
        assert supervisor.writer is None
        assert not config.evidence.exists()
    assert (config.sq03 / "signals.jsonl").exists()
    from sq04c_harness.isolation import write_json

    write_json(config.supervision / "session-report.json", report)


@pytest.mark.parametrize("scenario", ["accredited", "missing", "unobservable", "none"])
def test_s9_r3_real_composition_acceptance(
    config: HarnessConfig, scenario: str
) -> None:
    """Actual factory/strategy/gate/loop/recorder/async writer; no decision doubles."""
    import hashlib
    from dataclasses import asdict

    import cv2
    import numpy as np

    from pocket_option_analyzer.domain.strategy import StrategyProfile
    from pocket_option_analyzer.infrastructure.evidence.observational_evidence_writer import (  # noqa: E501
        ObservationalEvidenceWriter,
    )
    from sq04c_harness.composition import ObservedAnalysis
    from sq04c_harness.isolation import write_json
    from sq04c_harness.reconcile import IDENTITY, json_lines, sq03_records

    from .fixtures import s9_r3_frames

    frames = s9_r3_frames(scenario)
    budgets = dict(config.budgets, max_frame_bytes=frames[0].image.nbytes + 10)
    config = replace(config, max_cycles=len(frames), budgets=budgets)
    original_hashes = [hashlib.sha256(f.image.tobytes()).hexdigest() for f in frames]
    supervisor = build_synthetic(config, frames=frames)
    assert isinstance(supervisor.analysis, ObservedAnalysis)
    assert type(supervisor.writer) is ObservationalEvidenceWriter
    assert supervisor.pipeline.observational_evidence is supervisor.recorder
    assert supervisor.recorder.writer is supervisor.writer
    supervisor.start()
    try:
        completed = supervisor.done.wait(15)
    finally:
        report = supervisor.close(join_timeout=15, flush_timeout=15)
        write_json(config.supervision / "session-report.json", report)
        write_json(
            config.supervision / "composition-census.json",
            asdict(supervisor.analysis.census),
        )
        write_json(
            config.supervision / "synthetic-inputs.json",
            {
                "scenario": scenario,
                "market_claim": False,
                "budgets": budgets,
                "frames": [
                    {
                        "frame_id": f.frame_id,
                        "observed_at": f.created_at.isoformat(),
                        "monotonic_timestamp_ns": f.monotonic_timestamp_ns,
                        "source_key": f.source_key,
                        "shape": list(f.image.shape),
                        "chart_bytes": f.image.nbytes,
                        "chart_pixel_sha256": digest,
                        "context_bytes": (
                            0
                            if f.instrument_context_image is None
                            else f.instrument_context_image.nbytes
                        ),
                    }
                    for f, digest in zip(frames, original_hashes, strict=True)
                ],
            },
        )
    assert completed, report
    assert not report["errors"] and not report["observational_hook_errors"], report
    assert report["session_stopped"] and not report["worker_alive"]
    assert supervisor.recorder.pending_count == 0
    assert report["flush_result"] is True
    assert all(
        report["writer"][name] == 0
        for name in (
            "queued_items",
            "queued_bytes",
            "failure_count",
            "lost_event_count",
        )
    )
    assert report["metrics"]["evaluations"] == len(frames)
    assert original_hashes == [
        hashlib.sha256(f.image.tobytes()).hexdigest() for f in frames
    ]
    census = supervisor.analysis.census
    accepted, exits = sq03_records(config.sq03)
    assert census.acceptances == accepted
    if scenario == "none":
        assert not accepted and not exits and not census.evaluations
        assert report["state"] == "CLOSED_VERIFIED"
        assert (
            report["reconciliation"]["coverage"] == "NO_ACCEPTANCES_COVERAGE_INCOMPLETE"
        )
        return

    assert len(accepted) == len(exits) == 1, report
    identity, acceptance = next(iter(accepted.items()))
    entry, exit_record = acceptance["evaluation"], exits[identity]
    exit_evaluation = exit_record["exit_evaluation"]
    # All seven STRICT conditions are computed from pixels, with official profile.
    assert entry["evaluation_context_available"] is True
    assert entry["configuration"] == asdict(StrategyProfile.otc_precision_10s())
    assert (
        entry["audit"]["call"]["passed_count"]
        == entry["audit"]["call"]["total_count"]
        == 7
    )
    assert all(item["passed"] for item in entry["audit"]["call"]["conditions"].values())
    assert entry["frame_id"] == frames[0].frame_id
    assert entry["observed_at"] == frames[0].created_at.isoformat()
    assert identity == entry["evaluation_id"] + ":accepted"
    assert exit_record["entry_evaluation_id"] == entry["evaluation_id"]
    assert exit_record["event_id"] == identity + ":exit"
    assert exit_evaluation["frame_id"] == frames[-1].frame_id
    assert exit_evaluation["observed_at"] == frames[-1].created_at.isoformat()
    assert exit_evaluation["session_key"] == entry["session_key"]
    assert exit_evaluation["execution_id"] == entry["execution_id"]
    # Exact effective census: ONLY native accepted and selected exit identities.
    assert set(census.evaluations) == {
        entry["evaluation_id"],
        exit_evaluation["evaluation_id"],
    }
    assert len(census.observed_frames) == len(frames)
    assert all("evaluation_id" not in row for row in census.observed_frames)
    rows = json_lines(config.sq03 / "signals.jsonl")
    # SQ-03 coalesces duplicate-suppressed decisions; it is not a frame journal.
    assert 1 <= len(rows) <= len(frames)
    assert sum("accepted_evidence" in row for row in rows) == 1
    assert rows[0]["disposition"] == "actionable_accepted"
    assert rows[0]["direction"] == "call"
    assert rows[0]["is_actionable"] is True
    journal = json_lines(config.evidence / "events.jsonl")
    selected = [row for row in journal if row["event"] == "SQ03_EXIT_SELECTED"]
    assert len(selected) == 1
    assert selected[0]["exit_event_id"] == exit_record["event_id"]
    assert selected[0]["exit_evaluation_id"] == exit_evaluation["evaluation_id"]
    package = supervisor.writer.read_package(identity)  # same writer verifies disk
    assert package["closed"] and package["write_state"] == "WRITE_CONFIRMED"
    roles = package["roles"]
    for name, evaluation in (("ENTRY", entry), ("SQ03_EXIT", exit_evaluation)):
        assert roles[name]["state"] == "WRITE_CONFIRMED"
        assert all(roles[name]["frame"][key] == evaluation[key] for key in IDENTITY)
    for role in roles.values():
        for descriptor in role.get("images", {}).values():
            data = (config.evidence / descriptor["path"]).read_bytes()
            assert hashlib.sha256(data).hexdigest() == descriptor["sha256"]
            decoded = cv2.imdecode(
                np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_UNCHANGED
            )
            expected = next(
                f.image for f in frames if f.frame_id == role["frame"]["frame_id"]
            )
            assert np.array_equal(decoded, expected)
    pre = roles["PRE_EXPIRY"]
    if scenario == "missing":
        middle = frames[1]
        assert middle.instrument_context_image is not None
        assert (
            middle.image.nbytes + middle.instrument_context_image.nbytes
            > budgets["max_frame_bytes"]
        )
        assert pre == {"state": "PRE_EXPIRY_MISSING", "reason": "NO_FRAME"}
        assert package["package_state"] == "PACKAGE_PARTIAL"
    elif scenario == "accredited":
        assert pre["state"] == "WRITE_CONFIRMED"
        assert all(pre["frame"][key] == entry[key] for key in IDENTITY)
        assert package["package_state"] == "PACKAGE_COMPLETE"
    else:
        assert pre["state"] == "WRITE_CONFIRMED"
        assert pre["frame"]["frame_id"] == frames[1].frame_id
        assert pre["frame"]["evaluation_id"] not in census.evaluations
        assert package["package_state"] == "PACKAGE_COMPLETE"
        assert report["state"] == "CLOSE_UNVERIFIED"
        assert not report["reconciliation"]["verified"]
        assert any(
            "EVALUATION_IDENTITY_UNVERIFIED: PRE_EXPIRY" in issue
            for issue in report["reconciliation"]["issues"]
        )
        return
    assert report["state"] == "CLOSED_VERIFIED", report
    assert report["reconciliation"]["verified"]
    assert report["reconciliation"]["packages"] == {identity: package["package_state"]}


@pytest.mark.parametrize(
    "invalid", ["callback", "source", "pixels", "time", "count", "empty"]
)
def test_s9_r3_sequence_guard(config: HarnessConfig, invalid: str) -> None:
    from .fixtures import s9_r3_frames

    frames = s9_r3_frames("accredited")
    config = replace(config, max_cycles=len(frames))
    supplied: Any
    if invalid == "callback":

        def forbidden_callback() -> Any:
            pytest.fail("Capture callbacks must not execute")

        supplied = forbidden_callback
    elif invalid == "source":
        supplied = (replace(frames[0], source_key="LIVE"), frames[1])
    elif invalid == "pixels":
        supplied = (replace(frames[0], image=None), frames[1])
    elif invalid == "time":
        supplied = (frames[0], replace(frames[1], created_at=frames[0].created_at))
    elif invalid == "count":
        supplied = frames[:1]
    else:
        supplied = ()
    with pytest.raises(ValueError):
        build_synthetic(config, frames=supplied)
    assert not config.evidence.exists()
    assert not config.sq03.exists()
    assert not config.supervision.exists()


def test_s9_r3_sequence_exhaustion_does_not_replay() -> None:
    from .fixtures import s9_r3_frames

    frames = s9_r3_frames("accredited")
    source = SyntheticSource(frames=frames)
    assert source.capture_once() is frames[0]
    assert source.capture_once() is frames[1]
    with pytest.raises(RuntimeError, match="exhausted"):
        source.capture_once()
