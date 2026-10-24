from __future__ import annotations

import logging
from typing import Any

import pytest

from sq04c_harness.reconcile import Reconciliation
from sq04c_harness.supervisor import RecoveryApproval

from .fixtures import (
    FakeLoop,
    FakeWriter,
    NativePackage,
    exclusive_fixture_read,
    finished,
    make_supervisor,
    native_supervisor,
)


def test_continuous_session_normal_stop_and_metrics() -> None:
    loop = FakeLoop()
    supervisor = make_supervisor(loop)
    finished(supervisor)
    supervisor.poll()
    report = supervisor.close(join_timeout=1, flush_timeout=0)
    assert report["state"] == "CLOSED_VERIFIED"
    assert loop.started == loop.stopped == 1
    assert loop.cycles == report["metrics"]["evaluations"] == 2
    assert report["metrics"]["cycle_seconds"]["p95"] is not None
    assert report["metrics"]["samples"]
    assert report["metrics"]["measurement_scope"] == "SYNTHETIC_NOT_LIVE_PERFORMANCE"
    assert not report["durable_fsync_guaranteed"]
    assert report["flush_result"] is True
    assert [t["to"] for t in report["transitions"]] == [
        "CONFIGURED",
        "READY",
        "RUNNING",
        "STOP_REQUESTED",
        "SESSION_STOPPED",
        "FLUSHING",
        "RECONCILING",
        "CLOSED_VERIFIED",
    ]


def test_repeated_stop_and_close_do_not_repeat_session_or_flush() -> None:
    writer, loop = FakeWriter(), FakeLoop()
    supervisor = make_supervisor(loop, writer)
    finished(supervisor)
    supervisor.request_stop()
    supervisor.request_stop()
    first = supervisor.close(join_timeout=1, flush_timeout=0)
    assert supervisor.close(join_timeout=1, flush_timeout=0) == first
    assert writer.flush_calls == loop.stopped == 1
    with pytest.raises(RuntimeError, match="single-use"):
        supervisor.start()


def test_stop_waits_for_analysis_without_scheduling_more_cycles() -> None:
    loop = FakeLoop()
    loop.block = True
    supervisor = make_supervisor(loop)
    supervisor.start()
    try:
        assert loop.entered.wait(1)
        report = supervisor.close(join_timeout=0, flush_timeout=0)
        assert report["state"] == "CLOSE_UNVERIFIED"
        assert report["worker_alive"]
        assert supervisor.writer.flush_calls == 0
        assert supervisor.pipeline is not None
    finally:
        loop.release.set()
        assert supervisor.done.wait(2)
    assert (
        supervisor.close(join_timeout=1, flush_timeout=0)["state"] == "CLOSED_VERIFIED"
    )
    assert loop.cycles == 1


@pytest.mark.parametrize("phase", ["capture", "analysis", "session_close"])
def test_exceptions_preserve_traceback_and_never_report_verified(phase: str) -> None:
    loop = FakeLoop()
    if phase == "session_close":
        loop.close_error = True
    else:
        loop.cycle_error = f"synthetic {phase} exception"
    supervisor = make_supervisor(loop)
    finished(supervisor)
    report = supervisor.close(join_timeout=1, flush_timeout=0)
    assert report["state"] == "CLOSE_UNVERIFIED"
    assert any("Traceback" in error for error in report["errors"])
    assert supervisor.writer is not None


@pytest.mark.parametrize(
    "changes",
    [
        {"flush_value": False, "queued_items": 1, "queued_bytes": 64},
        {"flush_error": True},
        {"queued_items": 1, "queued_bytes": 64},
        {"lost_event_count": 1},
        {"failure_count": 1, "last_error": "EXPERIMENTAL_STORAGE_LIMIT"},
    ],
)
def test_flush_true_is_not_sufficient_and_errors_are_retained(
    changes: dict[str, Any],
) -> None:
    writer = FakeWriter()
    supervisor = make_supervisor(writer=writer)
    finished(supervisor)
    for name, value in changes.items():
        setattr(writer, name, value)
    report = supervisor.close(join_timeout=1, flush_timeout=0)
    assert report["state"] == "CLOSE_UNVERIFIED"
    assert supervisor.writer is writer
    assert writer.retry_calls == 0


def test_pending_acceptances_prevent_flush_success_claim() -> None:
    supervisor = make_supervisor()
    finished(supervisor)
    supervisor.recorder.pending_count = 1
    report = supervisor.close(join_timeout=1, flush_timeout=0)
    assert report["state"] == "CLOSE_UNVERIFIED"
    assert supervisor.writer.flush_calls == 0


def test_hook_fail_soft_logging_blocks_close() -> None:
    supervisor = make_supervisor()
    finished(supervisor)
    logging.getLogger(supervisor.logger.name).error(
        "Experimental originals failed at bind"
    )
    supervisor.poll()
    report = supervisor.close(join_timeout=1, flush_timeout=0)
    assert report["state"] == "CLOSE_UNVERIFIED"
    assert report["observational_hook_errors"]


def test_queue_stagnation_and_failure_growth_request_stop() -> None:
    loop = FakeLoop()
    loop.block = True
    writer = FakeWriter()
    supervisor = make_supervisor(loop, writer)
    supervisor.start()
    try:
        assert loop.entered.wait(1)
        writer.queued_items, writer.queued_bytes = 1, 64
        supervisor.poll(no_progress_seconds=0)
        assert supervisor.stop_event.is_set()
        assert supervisor.state == "STOP_REQUESTED"
    finally:
        loop.release.set()
        assert supervisor.done.wait(1)
    assert (
        supervisor.close(join_timeout=1, flush_timeout=0)["state"] == "CLOSE_UNVERIFIED"
    )


def test_supervised_transient_retry_once() -> None:
    # Legacy S8 case retained, with S9-R1's deliberately stricter public policy.
    writer = FakeWriter()
    supervisor = make_supervisor(writer=writer)
    finished(supervisor)
    writer.queued_items, writer.queued_bytes = 1, 64
    writer.failure_count = 1
    writer.last_error = "PermissionError: [WinError 32] transient sharing violation"
    writer.flush_value = False
    assert (
        supervisor.close(join_timeout=1, flush_timeout=0)["state"] == "CLOSE_UNVERIFIED"
    )
    approval = RecoveryApproval(("synthetic-acceptance",), 1, writer.last_error, True)
    with pytest.raises(ValueError, match="RETRY_UNVERIFIED"):
        supervisor.retry_once(approval)
    report = supervisor.close(join_timeout=1, flush_timeout=0)
    assert report["state"] == "CLOSE_UNVERIFIED"
    assert report["writer"]["failure_count"] == 1
    assert report["writer"]["last_error"] == approval.last_error
    assert report["recovery"] is None
    assert writer.queued_items == 1 and writer.queued_bytes == 64
    assert writer.retry_calls == 0
    with pytest.raises(ValueError, match="RETRY_UNVERIFIED"):
        supervisor.retry_once(approval)


@pytest.mark.parametrize(
    "error",
    [
        "UNSAFE_EVIDENCE_PATH",
        "MANIFEST_INTEGRITY_FAILURE",
        "ACCEPTANCE_IDENTITY_CONFLICT",
        "EXPERIMENTAL_STORAGE_LIMIT",
        "Unclassified failure",
    ],
)
def test_no_retry_for_confinement_corruption_or_unknown_cause(error: str) -> None:
    writer = FakeWriter()
    supervisor = make_supervisor(writer=writer)
    finished(supervisor)
    writer.failure_count, writer.queued_items = 1, 1
    writer.last_error, writer.flush_value = error, False
    supervisor.close(join_timeout=1, flush_timeout=0)
    with pytest.raises(ValueError):
        supervisor.retry_once(RecoveryApproval(("id",), 1, error, True))
    assert writer.retry_calls == 0


def test_failed_reconciliation_and_truthful_report() -> None:
    reconciliation = Reconciliation(
        False,
        {"id": "PACKAGE_FAILED"},
        ["PNG absent"],
        [],
        {},
        0,
        "SYNTHETIC",
    )
    supervisor = make_supervisor(reconciliation=reconciliation)
    finished(supervisor)
    report = supervisor.close(join_timeout=1, flush_timeout=0)
    assert report["state"] == "CLOSE_UNVERIFIED"
    assert report["reconciliation"]["issues"] == ["PNG absent"]
    assert not report["live_capture_performed"]


def test_no_discard_operation_exists_on_fake_writer() -> None:
    # All supervisor tests use this fake: calling discard_failed would fail.
    assert not hasattr(FakeWriter(), "discard_failed")


def test_retry_rejects_unknown_acceptance_identity() -> None:
    writer = FakeWriter()
    supervisor = make_supervisor(writer=writer)
    finished(supervisor)
    writer.failure_count, writer.queued_items, writer.queued_bytes = 1, 1, 64
    writer.last_error = "PermissionError: [WinError 32] synthetic sharing violation"
    writer.flush_value = False
    supervisor.close(join_timeout=1, flush_timeout=0)
    with pytest.raises(ValueError):
        supervisor.retry_once(
            RecoveryApproval(("unobserved-acceptance",), 1, writer.last_error, True)
        )
    assert writer.retry_calls == 0


def test_writer_failure_growth_stops_scheduling() -> None:
    loop, writer = FakeLoop(), FakeWriter()
    loop.block = True
    supervisor = make_supervisor(loop, writer)
    supervisor.start()
    try:
        assert loop.entered.wait(1)
        writer.failure_count = 1
        writer.last_error = "synthetic writer failure"
        supervisor.poll()
        assert supervisor.stop_event.is_set()
    finally:
        loop.release.set()
        assert supervisor.done.wait(1)
    assert (
        supervisor.close(join_timeout=1, flush_timeout=0)["state"] == "CLOSE_UNVERIFIED"
    )


@pytest.mark.parametrize(
    "scenario", ["transient", "mixed_same_acceptance", "mixed_acceptances"]
)
def test_s9_03_real_retained_tasks_cannot_be_classified_by_last_error(
    native_package: NativePackage,
    scenario: str,
) -> None:
    import json
    from types import SimpleNamespace

    fixture = native_package
    acceptances = [fixture.acceptance]
    if scenario == "mixed_acceptances":
        evaluation, frame = fixture.frame(1, 2)
        second = fixture.native.accept(
            evaluation,
            SimpleNamespace(
                signal=SimpleNamespace(direction=SimpleNamespace(value="call")),
                disposition=SimpleNamespace(value="actionable_accepted"),
                candle_interval_started_at=fixture.start,
            ),
            fixture.start,
            memory_only=True,
        )
        fixture.census.acceptance(second.to_dict())
        fixture.append(
            fixture.config.sq03 / "signals.jsonl",
            {"accepted_evidence": second.to_dict()},
        )
        fixture.recorder.accepted(second, frame)
        acceptances.append(second)
    fixture.partial()
    supervisor = native_supervisor(fixture)
    finished(supervisor)
    first_path = fixture.writer.package_path(fixture.identity)
    if scenario != "transient":
        payload = json.loads(first_path.read_text("utf-8"))
        payload["synthetic_integrity_fault"] = True  # Intentionally stale digest.
        first_path.write_text(json.dumps(payload), encoding="utf-8")
        assert fixture.writer.submit(acceptances[0].to_dict(), {}, closed=True)
        fixture.writer.drain()
        assert "MANIFEST_INTEGRITY_FAILURE" in fixture.writer.last_error
        assert fixture.writer.queued_items == 1
    target = acceptances[-1]
    with exclusive_fixture_read(fixture.writer.package_path(target.acceptance_id)):
        assert fixture.writer.submit(target.to_dict(), {}, closed=True)
        fixture.writer.drain()
        assert "[WinError 32]" in fixture.writer.last_error
    before = (
        fixture.writer.queued_items,
        fixture.writer.queued_bytes,
        fixture.writer.failure_count,
        fixture.writer.last_error,
    )
    assert before[0] == (1 if scenario == "transient" else 2)
    assert fixture.writer.lost_event_count == 0
    assert not fixture.writer.flush(0)
    assert (
        supervisor.close(join_timeout=2, flush_timeout=0)["state"] == "CLOSE_UNVERIFIED"
    )
    approval = RecoveryApproval(
        tuple(a.acceptance_id for a in acceptances), before[2], before[3], True
    )
    # Neither approval nor the latest global error identifies each retained task.
    with pytest.raises(ValueError, match="RETRY_UNVERIFIED"):
        supervisor.retry_once(approval)
    assert (
        fixture.writer.queued_items,
        fixture.writer.queued_bytes,
        fixture.writer.failure_count,
        fixture.writer.last_error,
    ) == before
    # Real drain performs no work: failed tasks were NOT moved back to its queue.
    fixture.writer.drain()
    assert (
        fixture.writer.queued_items,
        fixture.writer.queued_bytes,
        fixture.writer.failure_count,
        fixture.writer.last_error,
    ) == before
    assert (
        supervisor.close(join_timeout=2, flush_timeout=0)["state"] == "CLOSE_UNVERIFIED"
    )


@pytest.mark.parametrize(
    "fault, expected",
    [
        ("integrity", "MANIFEST_INTEGRITY_FAILURE"),
        ("identity", "ACCEPTANCE_IDENTITY_CONFLICT"),
        ("unknown", "JSONDecodeError"),
        ("confinement", "UNSAFE_EVIDENCE_PATH"),
        ("png", "EXISTING_ORIGINAL_CONFLICT"),
    ],
)
def test_s9_03_real_isolated_failures_preserve_tasks_and_diagnostics(
    native_package: NativePackage,
    fault: str,
    expected: str,
) -> None:
    import json
    import os

    import numpy as np

    fixture = native_package
    fixture.partial()
    supervisor = native_supervisor(fixture)
    finished(supervisor)
    path = fixture.writer.package_path(fixture.identity)
    original = path.read_bytes()
    acceptance = fixture.acceptance.to_dict()
    roles = {}
    exterior = fixture.config.evidence.parent / "outside-writer-sentinel.json"
    if fault == "integrity":
        payload = json.loads(original)
        payload["synthetic_integrity_fault"] = True
        path.write_text(json.dumps(payload), encoding="utf-8")
    elif fault == "identity":
        acceptance["direction"] = "put"
    elif fault == "unknown":
        path.write_bytes(b"{incomplete-synthetic-json")
    elif fault == "confinement":
        # Controlled hard link outside writer root, still inside this Temp fixture.
        # No personal directories, symlink privileges or private writer fields.
        os.link(path, exterior)
        assert path.stat().st_nlink == 2
    else:
        payload = json.loads(original)
        png = (
            fixture.writer.directory
            / payload["roles"]["ENTRY"]["images"]["chart"]["path"]
        )
        png.write_bytes(b"synthetic-corrupt-png")
        roles["ENTRY"] = fixture.recorder.capture(
            np.full((8, 8, 3), 1, dtype=np.uint8),
            None,
            None,
            fixture.acceptance.evaluation.to_dict(),
        )
        assert roles["ENTRY"] is not None
    assert fixture.writer.submit(acceptance, roles, closed=True)
    fixture.writer.drain()
    assert expected in fixture.writer.last_error
    before = (
        fixture.writer.queued_items,
        fixture.writer.queued_bytes,
        fixture.writer.failure_count,
        fixture.writer.last_error,
        fixture.writer.lost_event_count,
    )
    assert before[0] == 1 and before[2] > 0
    assert not fixture.writer.flush(0)
    assert (
        supervisor.close(join_timeout=2, flush_timeout=0)["state"] == "CLOSE_UNVERIFIED"
    )
    with pytest.raises(ValueError, match="RETRY_UNVERIFIED"):
        supervisor.retry_once(
            RecoveryApproval((fixture.identity,), before[2], before[3], True)
        )
    fixture.writer.drain()  # Must not have requeued any retained task.
    assert (
        fixture.writer.queued_items,
        fixture.writer.queued_bytes,
        fixture.writer.failure_count,
        fixture.writer.last_error,
        fixture.writer.lost_event_count,
    ) == before
    report = supervisor.close(join_timeout=2, flush_timeout=0)
    assert report["state"] == "CLOSE_UNVERIFIED"
    assert report["writer"]["last_error"] == before[3]
    assert report["recovery"] is None
    if fault == "confinement":
        assert exterior.read_bytes() == original
        assert path.read_bytes() == original
