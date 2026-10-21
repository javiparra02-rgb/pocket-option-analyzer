"""Same-evaluation telemetry; deliberately independent of outcome resolution."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from pocket_option_analyzer.domain.signals import SignalRecord


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Unsupported evidence value: {type(value).__name__}")


def json_snapshot(value: dict[str, Any]) -> str:
    """Detach telemetry from mutable last_* state, retaining float precision."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        default=_json_default,
    )


def dataclass_payload(value: Any) -> dict[str, Any] | None:
    if value is None or not is_dataclass(value) or isinstance(value, type):
        return None
    return asdict(value)


def price_payload(context: Any) -> dict[str, Any]:
    """Copy only price evidence, never masks, arrays, or a previous frame."""
    extraction = getattr(context, "current_visual_price", None)
    result = getattr(context, "reference_result", None)
    return {
        "reference": dataclass_payload(getattr(result, "reference", None)),
        "reference_diagnostic": dataclass_payload(result),
        "current_visual_price": (
            {
                "status": extraction.status.value,
                "price": dataclass_payload(extraction.price),
                "candidate_count": extraction.candidate_count,
                "selected_x": extraction.selected_x,
                "selected_y": extraction.selected_y,
                "confidence": extraction.confidence,
                "diagnostic": extraction.diagnostic,
            }
            if extraction is not None
            else None
        ),
        "chart_region": dataclass_payload(getattr(context, "chart_region", None)),
        "price_observation_region": dataclass_payload(
            getattr(context, "price_observation_region", None)
        ),
    }


@dataclass(frozen=True, slots=True)
class EvaluationEvidence:
    execution_id: str
    evaluation_id: str
    observed_at: datetime
    payload_json: str

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self.payload_json)  # type: ignore[no-any-return]


@dataclass(frozen=True, slots=True)
class AcceptedSignalEvidence:
    acceptance_id: str
    evaluation: EvaluationEvidence
    resolve_at: datetime
    payload_json: str

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self.payload_json)  # type: ignore[no-any-return]


@dataclass(frozen=True, slots=True)
class AcceptedSignalExitEvidence:
    acceptance_id: str
    event_id: str
    payload_json: str

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self.payload_json)  # type: ignore[no-any-return]


@dataclass(slots=True)
class _PendingAcceptance:
    evidence: AcceptedSignalEvidence
    record: SignalRecord
    persisted: bool = False
    memory_only: bool = False
    exit_evidence: AcceptedSignalExitEvidence | None = None


class AcceptedSignalEvidenceRecorder:
    """Owns IDs and pending telemetry, not trading, strategy, or the gate.

    Pending entries are intentionally not recovered after a process restart.
    Writer exceptions propagate; selected exit frames survive retries in memory.
    """

    def __init__(self) -> None:
        self.execution_id = uuid4().hex
        self._ordinal = 0
        self._pending: dict[str, _PendingAcceptance] = {}
        self.last_accepted: AcceptedSignalEvidence | None = None
        self.last_accepted_persisted = False
        self.last_exit: AcceptedSignalExitEvidence | None = None

    def capture(
        self, observed_at: datetime, payload: dict[str, Any]
    ) -> EvaluationEvidence:
        self._ordinal += 1
        evaluation_id = f"{self.execution_id}:{self._ordinal}"
        return EvaluationEvidence(
            self.execution_id,
            evaluation_id,
            observed_at,
            json_snapshot(
                {
                    **payload,
                    "execution_id": self.execution_id,
                    "evaluation_id": evaluation_id,
                }
            ),
        )

    def accept(
        self,
        evaluation: EvaluationEvidence,
        record: SignalRecord,
        gate_decided_at: datetime,
        *,
        memory_only: bool,
    ) -> AcceptedSignalEvidence:
        acceptance_id = f"{evaluation.evaluation_id}:accepted"
        resolve_at = evaluation.observed_at + timedelta(seconds=10)
        evidence = AcceptedSignalEvidence(
            acceptance_id,
            evaluation,
            resolve_at,
            json_snapshot(
                {
                    "schema": "accepted_signal_evidence",
                    "version": 1,
                    "acceptance_id": acceptance_id,
                    "evaluation": evaluation.to_dict(),
                    "direction": record.signal.direction.value,
                    "gate_disposition": record.disposition.value,
                    "gate_interval_started_at": (
                        record.candle_interval_started_at.isoformat()
                        if record.candle_interval_started_at is not None
                        else None
                    ),
                    "gate_decided_at": gate_decided_at.isoformat(),
                    "nominal_resolve_at": resolve_at.isoformat(),
                    "expiration_seconds": 10,
                    "presentation_at": None,
                    "executed_entry": False,
                }
            ),
        )
        self._pending[acceptance_id] = _PendingAcceptance(
            evidence, record, memory_only=memory_only
        )
        self.last_accepted = evidence
        self.last_accepted_persisted = False
        return evidence

    def persist_acceptance(
        self,
        acceptance_id: str,
        writer: Callable[[SignalRecord, AcceptedSignalEvidence], None],
    ) -> None:
        pending = self._pending[acceptance_id]
        if pending.persisted:
            return
        writer(pending.record, pending.evidence)
        pending.persisted = True
        if self.last_accepted is pending.evidence:
            self.last_accepted_persisted = True

    def observe_exits(
        self, evaluation: EvaluationEvidence
    ) -> tuple[AcceptedSignalExitEvidence, ...]:
        selected: list[AcceptedSignalExitEvidence] = []
        for pending in self._pending.values():
            if pending.exit_evidence is not None:
                continue
            entry_time = pending.evidence.evaluation.observed_at
            # Naive timestamps remain ambiguous; never guess their zone.
            if (
                entry_time.utcoffset() is None
                or evaluation.observed_at.utcoffset() is None
            ):
                continue
            if evaluation.observed_at < pending.evidence.resolve_at:
                continue
            entry = pending.evidence.evaluation.to_dict()
            current = evaluation.to_dict()
            # Another source/session is not an applicable observation.
            if any(
                entry.get(key) != current.get(key)
                for key in ("source", "source_key", "session_key")
            ):
                continue
            acceptance_id = pending.evidence.acceptance_id
            event_id = f"{acceptance_id}:exit"
            exit_evidence = AcceptedSignalExitEvidence(
                acceptance_id,
                event_id,
                json_snapshot(
                    {
                        "event_type": "accepted_signal_exit_evidence",
                        "version": 1,
                        "event_id": event_id,
                        "acceptance_id": acceptance_id,
                        "entry_evaluation_id": (
                            pending.evidence.evaluation.evaluation_id
                        ),
                        "nominal_resolve_at": pending.evidence.resolve_at.isoformat(),
                        "observed_at": evaluation.observed_at.isoformat(),
                        "lateness_seconds": (
                            evaluation.observed_at - pending.evidence.resolve_at
                        ).total_seconds(),
                        "source_identity_available": (
                            current.get("source_key") is not None
                            and current.get("session_key") is not None
                        ),
                        "exit_evaluation": current,
                    }
                ),
            )
            pending.exit_evidence = exit_evidence
            self.last_exit = exit_evidence
            selected.append(exit_evidence)
        return tuple(selected)

    def flush_exits(
        self, writer: Callable[[AcceptedSignalExitEvidence], bool] | None
    ) -> None:
        for acceptance_id, pending in tuple(self._pending.items()):
            if pending.exit_evidence is None:
                continue
            if pending.memory_only:
                del self._pending[acceptance_id]
            elif pending.persisted and writer is not None:
                if writer(pending.exit_evidence):
                    del self._pending[acceptance_id]
