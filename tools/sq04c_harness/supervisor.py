"""Cooperative session ownership with explicit, non-destructive close results."""

from __future__ import annotations

import logging
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from threading import Event, Lock, Thread
from time import monotonic
from typing import Any, Protocol

from .metrics import Metrics
from .reconcile import Reconciliation


class Loop(Protocol):
    def start_session(self) -> bool: ...
    def run_once(self) -> Any: ...
    def stop(self) -> None: ...
    def stop_session(self) -> None: ...


class Recorder(Protocol):
    @property
    def pending_count(self) -> int: ...


class Writer(Protocol):
    failure_count: int
    lost_event_count: int
    last_error: str | None
    last_write_seconds: float | None

    @property
    def queued_items(self) -> int: ...
    @property
    def queued_bytes(self) -> int: ...
    def flush(self, timeout: float) -> bool: ...
    def retry_failed(self, acceptance_id: str) -> int: ...


def writer_state(writer: Writer | None) -> dict[str, Any]:
    return {
        name: getattr(writer, name) if writer is not None else default
        for name, default in (
            ("queued_items", 0),
            ("queued_bytes", 0),
            ("failure_count", 0),
            ("lost_event_count", 0),
            ("last_error", None),
            ("last_write_seconds", None),
        )
    }


class HookErrors(logging.Handler):
    """Observe fail-soft originals errors without replacing any product method."""

    def __init__(self) -> None:
        super().__init__(level=logging.ERROR)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(self.format(record))


@dataclass(frozen=True)
class RecoveryApproval:
    """Request metadata only; not evidence of each retained task's failure cause."""

    acceptance_ids: tuple[str, ...]
    failure_count: int
    last_error: str
    transient_cause_resolved: bool


class Supervisor:
    """One use, one continuous session. References survive unverified closure.

    The owner calls poll() while running. No automatic retries or discards.
    All timeout values are supplied by the caller, not production thresholds.
    """

    def __init__(
        self,
        *,
        pipeline: Any,
        recorder: Recorder | None,
        writer: Writer | None,
        analysis: Any,
        loop: Loop,
        runtime: Any,
        reconcile: Callable[[], Reconciliation],
        metrics: Metrics,
        interval: float,
        max_cycles: int,
        known_acceptances: Callable[[], set[str]] | None = None,
    ) -> None:
        self.pipeline, self.recorder, self.writer = pipeline, recorder, writer
        self.analysis, self.loop, self.runtime = analysis, loop, runtime
        self.reconcile = reconcile
        self.metrics = metrics
        self.interval, self.max_cycles = interval, max_cycles
        self.known_acceptances = known_acceptances or (lambda: set())
        self.state = "CREATED"
        self.transitions: list[dict[str, Any]] = []
        self.errors: list[str] = []
        self.stop_event, self.done = Event(), Event()
        self.thread: Thread | None = None
        self.owner_lock = Lock()
        self.session_stopped = False
        self.flush_result: bool | None = None
        self.reconciliation: Reconciliation | None = None
        self.hook_errors = HookErrors()
        self.logger = logging.getLogger(
            "pocket_option_analyzer.application.signals.visual_signal_recording_pipeline"
        )
        self.initial_writer = writer_state(writer)
        self.retry_used = False
        self.recovery: dict[str, Any] | None = None
        self.last_progress = monotonic()
        self.last_queue: tuple[Any, ...] | None = None
        self._transition("CONFIGURED", "Explicit dependencies supplied")
        self._transition("READY", "Session not started")

    def _transition(self, state: str, reason: str) -> None:
        self.transitions.append(
            {
                "from": self.state,
                "to": state,
                "reason": reason,
                "monotonic": monotonic(),
            }
        )
        self.state = state

    def _worker(self) -> None:
        owns_session = False
        try:
            owns_session = self.loop.start_session()
            if not owns_session:
                raise RuntimeError("Session already owned by another caller")
            for _ in range(self.max_cycles):
                if self.stop_event.is_set():
                    break
                started = monotonic()
                evaluated = failed = False
                try:
                    evaluated = self.loop.run_once() is not None
                except Exception:
                    failed = True
                    raise
                finally:
                    self.metrics.cycle(
                        started, monotonic() - started, evaluated, failed
                    )
                if self.stop_event.wait(self.interval):
                    break
        except Exception:
            self.errors.append(traceback.format_exc())
            self.stop_event.set()
        finally:
            if owns_session:
                try:
                    self.loop.stop_session()
                    self.session_stopped = True
                except Exception:
                    self.errors.append(traceback.format_exc())
            self.done.set()

    def start(self) -> None:
        with self.owner_lock:
            if self.state != "READY":
                raise RuntimeError("Supervisor is single-use; double start rejected")
            self.logger.addHandler(self.hook_errors)
            self.thread = Thread(target=self._worker, name="sq04c-synthetic-supervisor")
            self._transition("RUNNING", "Supervisor owns acquisition scheduling")
            try:
                self.thread.start()
            except Exception:
                self.logger.removeHandler(self.hook_errors)
                self._transition("FAILED", "Worker could not start")
                raise

    def request_stop(self) -> None:
        with self.owner_lock:
            if self.state not in {"RUNNING", "STOP_REQUESTED", "CLOSE_UNVERIFIED"}:
                return
            self.stop_event.set()  # Set first: loop.stop alone doesn't gate run_once.
            try:
                self.loop.stop()
            except Exception:
                self.errors.append(traceback.format_exc())
            if self.state == "RUNNING":
                self._transition("STOP_REQUESTED", "No further cycles may be scheduled")

    def poll(self, *, no_progress_seconds: float | None = None) -> dict[str, Any]:
        snapshot = writer_state(self.writer)
        self.metrics.sample(snapshot)
        queue = (
            snapshot["queued_items"],
            snapshot["queued_bytes"],
            snapshot["last_write_seconds"],
        )
        now = monotonic()
        if queue != self.last_queue or not queue[0]:
            self.last_progress = now
            self.last_queue = queue
        stalled = (
            no_progress_seconds is not None
            and bool(queue[0])
            and now - self.last_progress >= no_progress_seconds
        )
        if (
            snapshot["failure_count"] > self.initial_writer["failure_count"]
            or snapshot["lost_event_count"] > self.initial_writer["lost_event_count"]
            or self.hook_errors.messages
            or stalled
        ):
            if stalled:
                self.errors.append(
                    "QUEUE_NO_PROGRESS: caller-supplied observation window"
                )
            self.request_stop()
        return snapshot

    def close(self, *, join_timeout: float, flush_timeout: float) -> dict[str, Any]:
        self.request_stop()
        with self.owner_lock:
            if self.state in {"CLOSED_VERIFIED", "FAILED"}:
                return self.report()
            if self.thread is None:
                raise RuntimeError("No started session to close")
            self.thread.join(timeout=join_timeout)
            if self.thread.is_alive() or not self.done.is_set():
                self._transition(
                    "CLOSE_UNVERIFIED", "Worker still active; references retained"
                )
                return self.report()
            self.logger.removeHandler(self.hook_errors)
            if not self.session_stopped:
                self._transition("CLOSE_UNVERIFIED", "Session stop not confirmed")
                return self.report()
            self._transition(
                "SESSION_STOPPED", "Worker joined; public stop_session returned"
            )
            if self.recorder is not None and self.recorder.pending_count:
                self._transition("CLOSE_UNVERIFIED", "Pending acceptances remain")
                return self.report()
            self._transition("FLUSHING", "Producer stopped before flush")
            self.metrics.sample(writer_state(self.writer))
            try:
                self.flush_result = (
                    self.writer.flush(flush_timeout)
                    if self.writer is not None
                    else True
                )
            except Exception:
                self.errors.append(traceback.format_exc())
                self.flush_result = None
            after = writer_state(self.writer)
            self.metrics.sample(after)
            if (
                self.flush_result is not True
                or after["queued_items"]
                or after["queued_bytes"]
            ):
                self._transition(
                    "CLOSE_UNVERIFIED", "Flush not verified or tasks retained"
                )
                return self.report()
            self._transition(
                "RECONCILING", "Queue drained, census/integrity still required"
            )
            try:
                self.reconciliation = self.reconcile()
            except Exception:
                self.errors.append(traceback.format_exc())
            healthy = (
                not self.errors
                and not self.hook_errors.messages
                and after["lost_event_count"] == 0
                and after["failure_count"] == 0
                and self.initial_writer["failure_count"] == 0
                and self.initial_writer["lost_event_count"] == 0
                and self.reconciliation is not None
                and self.reconciliation.verified
            )
            self._transition(
                "CLOSED_VERIFIED" if healthy else "CLOSE_UNVERIFIED",
                (
                    "Session, queue and census verified"
                    if healthy
                    else "Integrity, loss or execution errors remain documented"
                ),
            )
            return self.report()

    def retry_once(self, approval: RecoveryApproval) -> dict[str, int]:
        """Fail closed: the current public writer API has no per-task failure evidence.

        Keep the request surface so callers get an explicit rejection. Even an
        isolated observed WinError 32 is not proof about every retained task.
        Do not inspect private queues, requeue, discard, or erase diagnostics.
        """
        with self.owner_lock:
            if (
                self.state != "CLOSE_UNVERIFIED"
                or self.writer is None
                or self.thread is None
                or self.thread.is_alive()
                or not self.session_stopped
                or self.retry_used
            ):
                raise RuntimeError("Recovery requires stopped session and unused retry")
            raise ValueError(
                "RETRY_UNVERIFIED: public writer API cannot classify every retained "
                "task; retries disabled even with approval and a transient last_error"
            )

    def report(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "transitions": list(self.transitions),
            "session_stopped": self.session_stopped,
            "worker_alive": self.thread.is_alive() if self.thread else False,
            "flush_result": self.flush_result,
            "writer": writer_state(self.writer),
            "errors": list(self.errors),
            "observational_hook_errors": list(self.hook_errors.messages),
            "recovery": self.recovery,
            "retry_policy": "DISABLED_NO_PER_TASK_FAILURE_EVIDENCE",
            "metrics": self.metrics.report(),
            "reconciliation": (
                self.reconciliation.to_dict() if self.reconciliation else None
            ),
            "live_capture_performed": False,
            "market_outcome_claimed": False,
            "durable_fsync_guaranteed": False,
        }
