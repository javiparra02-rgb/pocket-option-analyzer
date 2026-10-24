from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from typing import Any

import pytest

from sq04c_harness.reconcile import reconcile

from .fixtures import NativePackage, finished, native_supervisor


def rewrite_manifest(fixture: NativePackage, payload: dict[str, Any]) -> None:
    payload.pop("manifest_sha256", None)
    raw = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")
    payload["manifest_sha256"] = hashlib.sha256(raw).hexdigest()
    fixture.writer.package_path(fixture.identity).write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )


def test_complete_native_package_integrity_and_exact_sq03_exit(
    native_package: NativePackage,
) -> None:
    native_package.complete()
    report = reconcile(
        native_package.writer, native_package.census, native_package.config.sq03
    )
    assert report.verified, report.issues
    assert report.packages == {native_package.identity: "PACKAGE_COMPLETE"}
    assert report.evidence_bytes > 0
    assert any(name.endswith(".png") for name in report.files)
    assert native_package.recorder.pending_count == 0
    assert (
        native_package.writer.read_package(native_package.identity)[
            "nominal_outcome_verified"
        ]
        is False
    )


def test_partial_justified_is_valid_not_complete(native_package: NativePackage) -> None:
    native_package.partial()
    report = reconcile(
        native_package.writer, native_package.census, native_package.config.sq03
    )
    assert report.verified, report.issues
    assert report.packages == {native_package.identity: "PACKAGE_PARTIAL"}
    package = native_package.writer.read_package(native_package.identity)
    assert package["write_state"] == "WRITE_CONFIRMED"
    assert package["roles"]["SQ03_EXIT"]["reason"] == "SESSION_STOPPED_OR_INTERRUPTED"


@pytest.mark.parametrize(
    "fault",
    [
        "manifest",
        "png_missing",
        "png_changed",
        "identity",
        "frame_identity",
        "no_absence_reason",
        "journal_missing",
        "extra_acceptance",
        "sq03_missing",
        "evidence_lost",
        "orphan_object",
        "temporary_file",
        "incomplete_package",
        "native_exit_mismatch",
        "duplicate_acceptance",
        "unknown_absence_reason",
        "older_pre",
        "missing_manifest_confirmation",
        "journal_evaluation_mismatch",
    ],
)
def test_reconciliation_rejects_faults(
    native_package: NativePackage, fault: str
) -> None:
    fixture = native_package
    if fault in {"no_absence_reason", "unknown_absence_reason"}:
        fixture.partial()
    else:
        fixture.complete()
    path = fixture.writer.package_path(fixture.identity)
    payload = json.loads(path.read_text("utf-8"))
    if fault == "manifest":
        path.write_text("{broken-json", encoding="utf-8")
    elif fault in {"png_missing", "png_changed"}:
        image = (
            fixture.writer.directory
            / payload["roles"]["ENTRY"]["images"]["chart"]["path"]
        )
        if fault == "png_missing":
            image.unlink()  # Only this synthetic fixture's own file.
        else:
            image.write_bytes(b"corrupt synthetic PNG")
    elif fault == "identity":
        payload["acceptance"]["acceptance_id"] = "substitution"
        rewrite_manifest(fixture, payload)
    elif fault == "frame_identity":
        payload["roles"]["ENTRY"]["frame"]["evaluation_id"] = "different-evaluation"
        rewrite_manifest(fixture, payload)
    elif fault == "no_absence_reason":
        del payload["roles"]["SQ03_EXIT"]["reason"]
        rewrite_manifest(fixture, payload)
    elif fault == "unknown_absence_reason":
        payload["roles"]["SQ03_EXIT"]["reason"] = "invented-justification"
        rewrite_manifest(fixture, payload)
    elif fault == "older_pre":
        role = payload["roles"]["PRE_EXPIRY"]
        role["frame"] = payload["roles"]["ENTRY"]["frame"]
        role["logical_identity"] = [
            fixture.identity,
            "PRE_EXPIRY",
            role["frame"]["frame_id"],
        ]
        rewrite_manifest(fixture, payload)
    elif fault in {"missing_manifest_confirmation", "journal_evaluation_mismatch"}:
        journal = fixture.writer.directory / "events.jsonl"
        events = [json.loads(line) for line in journal.read_text().splitlines()]
        if fault == "missing_manifest_confirmation":
            events = [e for e in events if e["event"] != "MANIFEST_WRITE_CONFIRMED"]
        else:
            for event in events:
                if event["event"] == "ACCEPTANCE_KNOWN":
                    event["evaluation_id"] = "substitution"
        journal.write_text(
            "".join(json.dumps(e) + "\n" for e in events), encoding="utf-8"
        )
    elif fault == "journal_missing":
        (fixture.writer.directory / "events.jsonl").unlink()
    elif fault in {"extra_acceptance", "duplicate_acceptance"}:
        fixture.writer.event(
            "other" if fault == "extra_acceptance" else fixture.identity,
            "ACCEPTANCE_KNOWN",
        )
    elif fault == "sq03_missing":
        (fixture.config.sq03 / "signals.jsonl").unlink()
    elif fault == "evidence_lost":
        fixture.writer.event(fixture.identity, "EVIDENCE_LOST", reason="QUEUE_LIMIT")
    elif fault in {"orphan_object", "temporary_file"}:
        (fixture.writer.directory / fault).write_bytes(b"synthetic orphan")
    elif fault == "incomplete_package":
        payload["closed"] = False
        rewrite_manifest(fixture, payload)
    elif fault == "native_exit_mismatch":
        payload["roles"]["SQ03_EXIT"]["frame"] = payload["roles"]["PRE_EXPIRY"]["frame"]
        rewrite_manifest(fixture, payload)
    report = reconcile(fixture.writer, fixture.census, fixture.config.sq03)
    assert not report.verified, fault
    assert report.issues


def test_native_retained_failure_and_quota_are_not_success(
    native_package: NativePackage,
) -> None:
    # New writer with tiny explicit quota in a different fixture-owned directory.
    from pocket_option_analyzer.infrastructure.evidence.observational_evidence_writer import (  # noqa: E501
        ObservationalEvidenceWriter,
    )

    cfg = replace(
        native_package.config.validate(),
        directory=native_package.config.evidence.parent / "quota",
        max_storage_bytes=1,
    )
    writer = ObservationalEvidenceWriter(cfg, background=False)
    writer.submit(native_package.acceptance.to_dict(), {"ENTRY": None}, closed=True)
    writer.drain()
    assert writer.failure_count > 0
    assert writer.lost_event_count > 0
    assert writer.queued_items == 1
    assert not writer.flush(0)
    # No discard: originals/tasks remain owned, test does not claim closure.


def test_native_reader_detects_restart_without_resuming_acquisition(
    native_package: NativePackage,
) -> None:
    fixture = native_package
    assert fixture.writer.flush(0)
    assert not fixture.writer.read_package(fixture.identity)["closed"]
    from pocket_option_analyzer.infrastructure.evidence.observational_evidence_writer import (  # noqa: E501
        ObservationalEvidenceWriter,
    )

    # Explicit restart fixture only; the supervisor never constructs a second writer.
    restarted = ObservationalEvidenceWriter(fixture.config.validate(), background=False)
    package = restarted.read_package(fixture.identity)
    assert package["closed"]
    assert "RESTART_BEFORE_COMPLETION" in package["failures"]
    assert package["roles"]["SQ03_EXIT"]["reason"] == "RESTART"
    report = reconcile(restarted, fixture.census, fixture.config.sq03)
    assert report.verified, report.issues
    assert report.packages[fixture.identity] == "PACKAGE_PARTIAL"


def test_independent_census_identity_conflicts_are_retained(
    native_package: NativePackage,
) -> None:
    fixture = native_package
    fixture.partial()
    alternative = fixture.acceptance.to_dict()
    alternative["direction"] = "put"
    fixture.census.acceptance(alternative)
    report = reconcile(fixture.writer, fixture.census, fixture.config.sq03)
    assert not report.verified
    assert any("identity conflict" in issue for issue in report.issues)


def rewrite_rows(path: Any, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


@pytest.mark.parametrize(
    "fault",
    [
        "entry_evaluation_id",
        "event_id",
        "journal_exit_event_id",
        "journal_exit_evaluation_id",
        "exit_evaluation_id",
        "nominal_resolve_at",
        "observed_at",
        "lateness_seconds",
        "journal_lateness_seconds",
        "missing_entry_evaluation_id",
        "missing_event_id",
        "missing_nominal_resolve_at",
        "missing_observed_at",
        "missing_lateness_seconds",
        "missing_exit_event_id",
        "missing_exit_evaluation_id",
        "missing_journal_lateness_seconds",
        "version",
        "source_identity_available",
    ],
)
def test_s9_01_exit_bindings_reject_contradictions(
    native_package: NativePackage,
    fault: str,
) -> None:
    fixture = native_package
    fixture.complete()
    assert reconcile(fixture.writer, fixture.census, fixture.config.sq03).verified
    output = fixture.config.sq03 / "observations.jsonl"
    rows = [json.loads(line) for line in output.read_text("utf-8").splitlines()]
    journal = fixture.writer.directory / "events.jsonl"
    events = [json.loads(line) for line in journal.read_text("utf-8").splitlines()]
    selection = next(e for e in events if e["event"] == "SQ03_EXIT_SELECTED")
    if fault in {"entry_evaluation_id", "event_id"}:
        rows[0][fault] = "different-native-identity"
    elif fault in {"journal_exit_event_id", "journal_exit_evaluation_id"}:
        selection[fault.removeprefix("journal_")] = "different-native-identity"
    elif fault == "exit_evaluation_id":
        rows[0]["exit_evaluation"]["evaluation_id"] = "different-native-identity"
    elif fault in {"nominal_resolve_at", "observed_at"}:
        rows[0][fault] = fixture.start.isoformat()
    elif fault == "lateness_seconds":
        rows[0][fault] = 999
    elif fault == "journal_lateness_seconds":
        selection["lateness_seconds"] = 999
    elif fault in {"missing_exit_event_id", "missing_exit_evaluation_id"}:
        del selection[fault.removeprefix("missing_")]
    elif fault == "missing_journal_lateness_seconds":
        del selection["lateness_seconds"]
    elif fault.startswith("missing_"):
        del rows[0][fault.removeprefix("missing_")]
    elif fault == "version":
        rows[0]["version"] = 2
    elif fault == "source_identity_available":
        rows[0]["source_identity_available"] = False
    else:
        raise AssertionError(fault)
    rewrite_rows(output, rows)
    rewrite_rows(journal, events)
    report = reconcile(fixture.writer, fixture.census, fixture.config.sq03)
    assert not report.verified, f"S9-01 contradiction accepted: {fault}"
    assert any("SQ03_EXIT_BINDING" in issue for issue in report.issues)
    supervisor = native_supervisor(fixture)
    finished(supervisor)
    assert (
        supervisor.close(join_timeout=2, flush_timeout=0)["state"] == "CLOSE_UNVERIFIED"
    )


@pytest.mark.parametrize(
    "fault", ["native_exit", "selection", "evaluation", "evaluation_observed_at"]
)
def test_s9_01_missing_exit_evidence_is_not_accredited(
    native_package: NativePackage,
    fault: str,
) -> None:
    fixture = native_package
    fixture.complete()
    output = fixture.config.sq03 / "observations.jsonl"
    journal = fixture.writer.directory / "events.jsonl"
    rows = [json.loads(line) for line in output.read_text("utf-8").splitlines()]
    if fault == "native_exit":
        rewrite_rows(output, [])
    elif fault == "selection":
        events = [json.loads(line) for line in journal.read_text("utf-8").splitlines()]
        rewrite_rows(journal, [e for e in events if e["event"] != "SQ03_EXIT_SELECTED"])
    else:
        if fault == "evaluation":
            del rows[0]["exit_evaluation"]
        else:
            del rows[0]["exit_evaluation"]["observed_at"]
        rewrite_rows(output, rows)
    report = reconcile(fixture.writer, fixture.census, fixture.config.sq03)
    assert not report.verified
    assert any("SQ03_EXIT_BINDING" in issue for issue in report.issues)
    supervisor = native_supervisor(fixture)
    finished(supervisor)
    assert (
        supervisor.close(join_timeout=2, flush_timeout=0)["state"] == "CLOSE_UNVERIFIED"
    )


@pytest.mark.parametrize("present", [False, True])
def test_s9_02_native_pre_present_verified_or_legitimately_absent(
    native_package: NativePackage,
    present: bool,
) -> None:
    import numpy as np

    fixture = native_package
    if present:
        fixture.complete()
    else:
        evaluation, _ = fixture.frame(9, 2)
        unsupported = fixture.recorder.capture(
            np.zeros((8, 8, 3), dtype=np.float32),
            None,
            None,
            evaluation.to_dict(),
        )
        assert unsupported is None
        assert fixture.recorder.candidate_failure == "UNSUPPORTED_IMAGE"
        fixture.recorder.observed(evaluation, unsupported, ())
        fixture.partial()  # Native stop supplies SESSION_STOPPED_OR_INTERRUPTED.
    report = reconcile(fixture.writer, fixture.census, fixture.config.sq03)
    assert report.verified, report.issues
    package = fixture.writer.read_package(fixture.identity)
    role = package["roles"]["PRE_EXPIRY"]
    if present:
        assert role["frame"]["evaluation_id"] in fixture.census.evaluations
        assert role["state"] == "WRITE_CONFIRMED"
        assert report.packages[fixture.identity] == "PACKAGE_COMPLETE"
    else:
        assert role["state"] == "PRE_EXPIRY_MISSING"
        assert role["reason"] == "SESSION_STOPPED_OR_INTERRUPTED"
        assert "frame" not in role and "images" not in role
        assert report.packages[fixture.identity] == "PACKAGE_PARTIAL"
    supervisor = native_supervisor(fixture)
    finished(supervisor)
    assert (
        supervisor.close(join_timeout=2, flush_timeout=0)["state"] == "CLOSED_VERIFIED"
    )


def test_s9_02_observed_analysis_does_not_expose_intermediate_native_id(
    native_package: NativePackage,
) -> None:
    from types import SimpleNamespace

    from sq04c_harness.composition import ObservedAnalysis, SyntheticFrame
    from sq04c_harness.reconcile import Census

    fixture = native_package
    evaluation, original = fixture.frame(9, 2)
    fixture.recorder.observed(evaluation, original, ())
    census = Census()
    calls = []
    # Public native SQ03 objects, with a non-strategy delegate solely for the
    # composition observation contract. No manufactured evaluation return field.
    delegate = SimpleNamespace(execute=lambda frame: calls.append(frame))
    observer = ObservedAnalysis(
        delegate,
        SimpleNamespace(accepted_evidence=fixture.native),
        census,
    )
    observer.session_key = "synthetic-session"
    frame = SyntheticFrame(None, 2, evaluation.observed_at, 9_000_000_000)
    observer.execute(frame)
    assert calls == [frame]
    assert fixture.identity in census.acceptances
    assert fixture.acceptance.evaluation.evaluation_id in census.evaluations
    assert evaluation.evaluation_id not in census.evaluations
    assert len(census.observed_frames) == 1
    assert "evaluation_id" not in census.observed_frames[0]
    fixture.partial()


@pytest.mark.parametrize("substituted", [False, True])
def test_s9_02_sparse_realistic_census_cannot_accredit_pre(
    native_package: NativePackage,
    substituted: bool,
) -> None:
    fixture = native_package
    fixture.complete()
    path = fixture.writer.package_path(fixture.identity)
    payload = json.loads(path.read_text("utf-8"))
    frame = payload["roles"]["PRE_EXPIRY"]["frame"]
    original_id = frame["evaluation_id"]
    assert original_id != fixture.acceptance.evaluation.evaluation_id
    assert (
        original_id
        != fixture.native.last_exit.to_dict()["exit_evaluation"]["evaluation_id"]
    )
    # This is precisely what ObservedAnalysis retains for an intermediate frame.
    fixture.census.observed_frames.append(
        {
            key: frame[key]
            for key in (
                "frame_id",
                "observed_at",
                "source",
                "source_key",
                "session_key",
            )
        }
    )
    del fixture.census.evaluations[original_id]
    if substituted:
        frame["evaluation_id"] = "unobserved-evaluation-id"
        rewrite_manifest(fixture, payload)
    report = reconcile(fixture.writer, fixture.census, fixture.config.sq03)
    assert not report.verified, "S9-02 unaccredited PRE accepted through frame fallback"
    assert any("EVALUATION_IDENTITY_UNVERIFIED" in issue for issue in report.issues)
    supervisor = native_supervisor(fixture)
    finished(supervisor)
    assert (
        supervisor.close(join_timeout=2, flush_timeout=0)["state"] == "CLOSE_UNVERIFIED"
    )
