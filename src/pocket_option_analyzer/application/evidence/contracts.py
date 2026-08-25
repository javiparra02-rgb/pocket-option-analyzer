from __future__ import annotations

from typing import Protocol, runtime_checkable

from .identity_shadow import IdentityShadowFrameEvidence
from .models import VisualEvidenceAssociation, VisualFrameEvidence


@runtime_checkable
class VisualEvidenceRecorder(Protocol):
    """Application port for synchronous, in-memory visual evidence delivery."""

    def record_frame(
        self,
        frame_evidence: VisualFrameEvidence,
        associations: tuple[VisualEvidenceAssociation, ...],
    ) -> None: ...


@runtime_checkable
class IdentityShadowEvidenceRecorder(Protocol):
    """Dedicated port for continuous, non-authoritative identity evidence."""

    def start_identity_session(self, *, session_key: str) -> None: ...

    def record_identity_shadow(
        self,
        frame_evidence: IdentityShadowFrameEvidence,
    ) -> None: ...

    def stop_identity_session(self) -> None: ...
