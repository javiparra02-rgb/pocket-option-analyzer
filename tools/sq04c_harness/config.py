"""Explicit experiment configuration; live modes deliberately have no backend."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Any

from .isolation import IsolationError, outside, require_active_snapshot


@dataclass(frozen=True)
class HarnessConfig:
    mode: str
    capture_observational: bool
    pipeline_observational: bool
    budgets: dict[str, Any]
    interval_seconds: float
    join_timeout: float
    flush_timeout: float
    max_cycles: int
    sample_capacity: int
    snapshot: Path
    repository: Path
    evidence: Path
    sq03: Path
    supervision: Path

    def validate(self) -> Any:
        if self.mode != "SYNTHETIC":
            raise ValueError("Real OFF/ON acquisition requires a future authorization")
        if (
            type(self.capture_observational) is not bool
            or type(self.pipeline_observational) is not bool
        ):
            raise ValueError("Observational switches must be explicit booleans")
        if self.capture_observational != self.pipeline_observational:
            raise ValueError("Capture/pipeline observational configuration mismatch")
        for name in ("max_cycles", "sample_capacity"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 1:
                raise ValueError(f"{name} must be a positive integer")
        if self.max_cycles > self.sample_capacity:
            raise ValueError("Sample capacity must cover the bounded synthetic run")
        for name in ("interval_seconds", "join_timeout", "flush_timeout"):
            value = getattr(self, name)
            if type(value) not in (int, float) or not isfinite(value) or value < 0:
                raise ValueError(f"Invalid finite timeout/interval: {name}")
        required = {
            "max_frame_bytes",
            "max_retained_bytes",
            "max_pending_acceptances",
            "max_queue_items",
            "max_queue_bytes",
            "max_storage_bytes",
            "pending_retention_seconds",
            "context_region",
        }
        if set(self.budgets) != required:
            raise ValueError("Complete explicit observational budgets required")
        if isinstance(self.budgets["pending_retention_seconds"], bool):
            raise ValueError("Boolean retention is not admitted")
        outputs = (self.evidence, self.sq03, self.supervision)
        for i, path in enumerate(outputs):
            outside(path, self.repository, self.snapshot, *outputs[:i])
        if not self.snapshot.is_dir():
            raise IsolationError("Missing prepared snapshot")
        require_active_snapshot(self.snapshot)
        # This import is permitted only after activate_snapshot in the launcher.
        from pocket_option_analyzer.application.evidence.observational_evidence import (
            ObservationalEvidenceConfig,
        )

        return ObservationalEvidenceConfig(directory=self.evidence, **self.budgets)
