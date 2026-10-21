"""Opt-in mode-A originals. No prices, outcomes, or nominal-time assertions."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from time import monotonic
from typing import Any, Protocol

import numpy as np

from pocket_option_analyzer.application.signals.accepted_signal_evidence import (
    AcceptedSignalEvidence,
    AcceptedSignalExitEvidence,
    EvaluationEvidence,
    dataclass_payload,
    json_snapshot,
)


@dataclass(frozen=True, slots=True)
class ObservationalEvidenceConfig:
    """All budgets are explicit: no guessed production FPS/disk defaults.

    max_frame_bytes bounds the candidate copy; max_retained_bytes bounds pinned
    candidates; queue budgets include in-flight work. Retention is operational,
    never an admissible expiry tolerance. directory must be outside the repo.
    """

    directory: Path
    max_frame_bytes: int
    max_retained_bytes: int
    max_pending_acceptances: int
    max_queue_items: int
    max_queue_bytes: int
    max_storage_bytes: int
    pending_retention_seconds: float
    context_region: tuple[int, int, int, int] | None = None

    def __post_init__(self) -> None:
        from math import isfinite

        for name in (
            "max_frame_bytes",
            "max_retained_bytes",
            "max_pending_acceptances",
            "max_queue_items",
            "max_queue_bytes",
            "max_storage_bytes",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        if (
            not isfinite(self.pending_retention_seconds)
            or self.pending_retention_seconds <= 0
        ):
            raise ValueError("Retention must be finite and positive")
        if self.max_retained_bytes < self.max_frame_bytes:
            raise ValueError("Retained budget must accommodate one candidate")
        if self.context_region is not None:
            x, y, width, height = self.context_region
            if any(type(v) is not int for v in self.context_region):
                raise ValueError("Context geometry must use integers")
            if x < 0 or y < 0 or width < 1 or height < 1:
                raise ValueError("Invalid context region")


@dataclass(frozen=True, slots=True)
class OriginalFrame:
    metadata_json: str
    images: tuple[tuple[str, np.ndarray], ...]

    @property
    def nbytes(self) -> int:
        return sum(image.nbytes for _, image in self.images)


class OriginalEvidenceWriter(Protocol):
    def event(self, acceptance_id: str, event: str, **details: Any) -> bool: ...

    def submit(
        self,
        acceptance: dict[str, Any],
        roles: dict[str, OriginalFrame | None],
        *,
        closed: bool,
        reason: str | None = None,
    ) -> bool: ...


@dataclass(slots=True)
class _PendingOriginals:
    evidence: AcceptedSignalEvidence
    entry: OriginalFrame | None
    pre: OriginalFrame | None
    started: float


class ObservationalEvidenceRecorder:
    """Bounded pinning of actual inputs; exit selection belongs ONLY to SQ-03."""

    def __init__(
        self,
        config: ObservationalEvidenceConfig,
        writer: OriginalEvidenceWriter,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self.config = config
        self.writer = writer
        self._clock = clock
        self._pending: dict[str, _PendingOriginals] = {}
        self._last_observed_at: datetime | None = None
        self.candidate_failure: str | None = None

    @property
    def retained_bytes(self) -> int:
        unique = {
            id(frame): frame.nbytes
            for pending in self._pending.values()
            for frame in (pending.entry, pending.pre)
            if frame is not None
        }
        return sum(unique.values())

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    def capture(
        self,
        image: np.ndarray,
        price_image: np.ndarray | None,
        context_image: np.ndarray | None,
        metadata: dict[str, Any],
    ) -> OriginalFrame | None:
        self.candidate_failure = None
        originals = [("chart", image)]
        if price_image is not None:
            originals.append(("price_observation", price_image))
        if context_image is not None:
            originals.append(("instrument_context", context_image))
        size = sum(array.nbytes for _, array in originals)
        if size > self.config.max_frame_bytes:
            self.candidate_failure = "FRAME_BYTE_LIMIT"
            return None
        copies = []
        for role, array in originals:
            if array.dtype != np.uint8 or array.ndim not in (2, 3):
                self.candidate_failure = "UNSUPPORTED_IMAGE"
                return None
            owned = array.copy(order="C")
            owned.flags.writeable = False
            copies.append((role, owned))
        return OriginalFrame(json_snapshot(metadata), tuple(copies))

    def accepted(
        self, evidence: AcceptedSignalEvidence, frame: OriginalFrame | None
    ) -> None:
        identity = evidence.acceptance_id
        if identity in self._pending:
            self.writer.event(identity, "DUPLICATE_ACCEPTANCE")
            return
        if frame is not None and not self._matches(frame, evidence.evaluation):
            frame = None
            self.candidate_failure = "FRAME_IDENTITY_MISMATCH"
        self.writer.event(
            identity,
            "ACCEPTANCE_KNOWN",
            evaluation_id=(evidence.evaluation.evaluation_id),
        )
        overflow = (
            len(self._pending) >= self.config.max_pending_acceptances
            or self.retained_bytes + (frame.nbytes if frame else 0)
            > self.config.max_retained_bytes
        )
        self.writer.submit(
            evidence.to_dict(),
            {"ENTRY": frame},
            closed=overflow,
            reason="RETENTION_LIMIT" if overflow else self.candidate_failure,
        )
        if overflow:
            self.writer.event(identity, "EVIDENCE_LOST", reason="RETENTION_LIMIT")
            return
        self._pending[identity] = _PendingOriginals(
            evidence, frame, frame, self._clock()
        )

    def bind(
        self, frame: OriginalFrame | None, evaluation: EvaluationEvidence
    ) -> OriginalFrame | None:
        if frame is None:
            return None
        context = evaluation.to_dict()
        metadata = json.loads(frame.metadata_json)
        metadata.update(
            {
                key: context.get(key)
                for key in (
                    "execution_id",
                    "evaluation_id",
                    "snapshot_id",
                    "analysis_started_at",
                    "analysis_completed_at",
                )
            }
        )
        return replace(frame, metadata_json=json_snapshot(metadata))

    def observed(
        self,
        evaluation: EvaluationEvidence,
        frame: OriginalFrame | None,
        selected_exits: tuple[AcceptedSignalExitEvidence, ...],
    ) -> None:
        selected = {item.acceptance_id: item for item in selected_exits}
        current = evaluation.to_dict()
        if frame is not None and not self._matches(frame, evaluation):
            frame = None
            self.candidate_failure = "FRAME_IDENTITY_MISMATCH"
        regressed = (
            self._last_observed_at is not None
            and self._last_observed_at.utcoffset() is not None
            and evaluation.observed_at.utcoffset() is not None
            and evaluation.observed_at < self._last_observed_at
        )
        self._last_observed_at = evaluation.observed_at
        for identity, pending in tuple(self._pending.items()):
            if regressed:
                self.writer.event(identity, "WALL_CLOCK_REGRESSION")
            exit_evidence = selected.get(identity)
            if exit_evidence is not None:
                # No alternative selector, no substitution on a later frame.
                self.writer.submit(
                    pending.evidence.to_dict(),
                    {"PRE_EXPIRY": pending.pre, "SQ03_EXIT": frame},
                    closed=True,
                    reason=self.candidate_failure,
                )
                self.writer.event(
                    identity,
                    "SQ03_EXIT_SELECTED",
                    **{
                        "exit_event_id": exit_evidence.event_id,
                        "exit_evaluation_id": evaluation.evaluation_id,
                        "lateness_seconds": exit_evidence.to_dict()["lateness_seconds"],
                    },
                )
                del self._pending[identity]
                continue
            if self._clock() - pending.started >= self.config.pending_retention_seconds:
                self._finish(identity, "RETENTION_EXPIRED")
                continue
            entry = pending.evidence.evaluation.to_dict()
            if any(
                entry.get(k) != current.get(k)
                for k in ("source", "source_key", "session_key")
            ):
                continue
            if (
                evaluation.observed_at.utcoffset() is None
                or pending.evidence.resolve_at.utcoffset() is None
            ):
                self.writer.event(identity, "TEMPORAL_REFERENCE_UNCERTAIN")
                continue
            if evaluation.observed_at < pending.evidence.resolve_at:
                previous = pending.pre
                pending.pre = frame
                if self.retained_bytes > self.config.max_retained_bytes:
                    pending.pre = None
                    self.writer.event(
                        identity, "EVIDENCE_LOST", reason="PRE_BYTE_LIMIT"
                    )
                del previous

    @staticmethod
    def _matches(frame: OriginalFrame, evaluation: EvaluationEvidence) -> bool:
        metadata = json.loads(frame.metadata_json)
        context = evaluation.to_dict()
        return all(
            metadata.get(key) == context.get(key)
            for key in (
                "frame_id",
                "observed_at",
                "source",
                "source_key",
                "session_key",
                "evaluation_id",
                "execution_id",
            )
        )

    def signal_status(self, acceptance_id: str, state: str) -> None:
        self.writer.event(acceptance_id, "SQ03_SIGNAL_WRITE", state=state)

    def _finish(self, identity: str, reason: str) -> None:
        pending = self._pending.pop(identity)
        self.writer.submit(
            pending.evidence.to_dict(),
            {"PRE_EXPIRY": pending.pre, "SQ03_EXIT": None},
            closed=True,
            reason=reason,
        )

    def stop_session(self) -> None:
        for identity in tuple(self._pending):
            self._finish(identity, "SESSION_STOPPED_OR_INTERRUPTED")


def original_metadata(
    *,
    frame_id: int | None,
    observed_at: str,
    source: str,
    source_key: str | None,
    session_key: str | None,
    chart_region: Any,
    price_region: Any,
    capture_metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "frame_id": frame_id,
        "observed_at": observed_at,
        "source": source,
        "source_key": source_key,
        "session_key": session_key,
        "geometry": {
            "chart": dataclass_payload(chart_region),
            "price_observation": dataclass_payload(price_region),
        },
        # capture() serializes/detaches this inside the fail-soft hook.
        "capture": capture_metadata or {},
        "instrument_identity": "UNKNOWN",
        "quote_effective_at": None,
        "mode": "OBSERVATIONS_ONLY",
        "nominal_outcome_authorized": False,
    }
