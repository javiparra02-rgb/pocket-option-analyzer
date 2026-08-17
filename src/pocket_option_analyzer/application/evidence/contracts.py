from __future__ import annotations

from typing import Protocol, runtime_checkable

from .models import VisualEvidenceAssociation, VisualFrameEvidence


@runtime_checkable
class VisualEvidenceRecorder(Protocol):
    """Application port for synchronous, in-memory visual evidence delivery."""

    def record_frame(
        self,
        frame_evidence: VisualFrameEvidence,
        associations: tuple[VisualEvidenceAssociation, ...],
    ) -> None: ...
