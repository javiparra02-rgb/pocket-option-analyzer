from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import tempfile
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from time import perf_counter
from typing import Any

import cv2
import numpy as np

from pocket_option_analyzer.application.evidence import (
    IdentityShadowEventType,
    IdentityShadowEvidenceConfig,
    IdentityShadowFrameEvidence,
    IdentityShadowPngMode,
    VisualEvidenceAssociation,
    VisualFrameEvidence,
)
from pocket_option_analyzer.application.market import (
    CurrentCandleIdentityLifecycle,
    CurrentCandleIdentityResetReason,
    CurrentCandleIdentitySource,
    CurrentCandleIdentityStatus,
    CurrentCandleIdentityTrace,
)

from .identity_shadow_evidence_reader import IdentityShadowEvidenceReader
from .identity_shadow_evidence_serializer import (
    IdentityShadowEvidenceSerializer,
)
from .visual_evidence_serializer import VisualEvidenceSerializer

logger = logging.getLogger(__name__)

PngEncoder = Callable[[np.ndarray], bytes]
Clock = Callable[[], datetime]
Timer = Callable[[], float]


class FilesystemVisualEvidenceRecorder:
    """Synchronous filesystem adapter for selected visual evidence.

    The adapter consumes the arrays borrowed by ``VisualFrameEvidence`` during
    the same tick. It does not capture or copy source frames. If persistence is
    made asynchronous in the future, callers must copy or explicitly transfer
    array ownership before the tick ends.
    """

    SCHEMA_VERSION = 1

    def __init__(
        self,
        directory: Path,
        *,
        application_version: str | None = None,
        observation_jsonl_path: Path | None = None,
        source_commit: str | None = None,
        identity_evidence_config: IdentityShadowEvidenceConfig | None = None,
        png_encoder: PngEncoder | None = None,
        clock: Clock | None = None,
        timer: Timer | None = None,
    ) -> None:
        self._directory = Path(directory)
        self._frames_directory = self._directory / "frames"
        self._snapshots_directory = self._directory / "snapshots"
        self._manifest_path = self._directory / "manifest.jsonl"
        self._failures_path = self._directory / "failures.jsonl"
        self._application_version = application_version
        self._observation_jsonl_path = observation_jsonl_path
        self._source_commit = source_commit
        self._identity_config = identity_evidence_config
        self._png_encoder = png_encoder or self._default_png_encoder
        self._clock = clock or (lambda: datetime.now(UTC))
        self._timer = timer or perf_counter
        self._frame_keys_by_id: dict[int, str] = {}
        self._manifest_associations: set[tuple[str, str]] = set()
        self._identity_lock = RLock()
        self._identity_session_key: str | None = None
        self._identity_frames_path = self._directory / "identity_shadow/frames.jsonl"
        self._identity_events_path = self._directory / "identity_shadow/events.jsonl"
        self._identity_png_directory = self._directory / "identity_shadow/png"
        self._identity_frame_count = 0
        self._identity_event_count = 0
        self._identity_previous_frame_hash: str | None = None
        self._identity_previous_event_hash: str | None = None
        self._identity_previous_trace: CurrentCandleIdentityTrace | None = None
        self._identity_seen_frame_keys: set[str] = set()
        self._identity_ring: deque[dict[str, Any]] = deque(
            maxlen=(
                identity_evidence_config.ring_buffer_size
                if identity_evidence_config is not None
                else 1
            )
        )

        self._directory.mkdir(parents=True, exist_ok=True)
        self._frames_directory.mkdir(parents=True, exist_ok=True)
        self._snapshots_directory.mkdir(parents=True, exist_ok=True)
        self._initialize_session_metadata()
        self._ensure_append_file(self._manifest_path)
        self._ensure_append_file(self._failures_path)
        self._load_existing_frames()
        self._load_manifest()

    @property
    def directory(self) -> Path:
        return self._directory

    def record_frame(
        self,
        frame_evidence: VisualFrameEvidence,
        associations: tuple[VisualEvidenceAssociation, ...],
    ) -> None:
        if not associations:
            return
        started_at = self._timer()
        stage = "publish_frame"
        relevant_paths: list[str] = []
        try:
            expected_frame_key = self.frame_key(frame_evidence)
            relevant_paths.append(f"frames/{expected_frame_key}")
            frame_key, frame_created, png_bytes = self._publish_frame(
                frame_evidence,
            )
            for association in associations:
                stage = "publish_association"
                snapshot_key = self.snapshot_key(association.snapshot_id)
                association_path = (
                    f"snapshots/{snapshot_key}/{association.phase.value}.json"
                )
                relevant_paths.append(association_path)
                association_created = self._publish_association(
                    frame_evidence=frame_evidence,
                    frame_key=frame_key,
                    snapshot_key=snapshot_key,
                    association=association,
                )
                if not association_created:
                    continue
                stage = "append_manifest"
                elapsed_ms = (self._timer() - started_at) * 1000.0
                manifest_appended = self._append_manifest(
                    {
                        "schema_version": self.SCHEMA_VERSION,
                        "snapshot_id": association.snapshot_id,
                        "snapshot_key": snapshot_key,
                        "phase": association.phase.value,
                        "frame_key": frame_key,
                        "frame_id": frame_evidence.frame_id,
                        "frame_timestamp": (
                            frame_evidence.frame_timestamp.isoformat()
                        ),
                        "recorded_at": self._aware_utc_now().isoformat(),
                        "frame_created": frame_created,
                        "png_bytes_written": png_bytes if frame_created else 0,
                        "record_frame_duration_ms_before_manifest_append": (
                            elapsed_ms
                        ),
                    }
                )
                self._manifest_associations.add(
                    (association.snapshot_id, association.phase.value)
                )
                if manifest_appended:
                    frame_created = False
                    png_bytes = 0
        except Exception as error:
            self._record_failure_if_possible(
                error=error,
                stage=stage,
                frame_id=frame_evidence.frame_id,
                snapshot_ids=tuple(
                    association.snapshot_id for association in associations
                ),
                relevant_paths=tuple(relevant_paths),
            )
            raise

    def start_identity_session(self, *, session_key: str) -> None:
        """Initialize the opt-in identity stream without touching analysis."""

        if self._identity_config is None:
            return
        if not session_key:
            raise ValueError("session_key cannot be empty.")
        with self._identity_lock:
            if self._identity_session_key is not None:
                self._stop_identity_session_locked()
            self._identity_png_directory.mkdir(parents=True, exist_ok=True)
            self._ensure_append_file(self._identity_frames_path)
            self._ensure_append_file(self._identity_events_path)
            self._load_identity_streams()
            self._identity_session_key = session_key
            self._identity_previous_trace = None
            self._identity_ring.clear()
            self._append_identity_event(
                event_type=IdentityShadowEventType.LIFECYCLE_START,
                session_key=session_key,
                frame_payload=None,
                previous_status=None,
                png=None,
            )

    def stop_identity_session(self) -> None:
        """Synchronously finish one identity evidence lifecycle."""

        if self._identity_config is None:
            return
        with self._identity_lock:
            self._stop_identity_session_locked()

    def record_identity_shadow(
        self,
        frame_evidence: IdentityShadowFrameEvidence,
    ) -> None:
        """Persist one compact same-pass trace; failures remain diagnostic."""

        if self._identity_config is None:
            return
        with self._identity_lock:
            try:
                self._record_identity_shadow_locked(frame_evidence)
            except Exception as error:  # noqa: BLE001 - diagnostic fail-soft port.
                self._record_identity_failure(frame_evidence, error)

    def _record_identity_shadow_locked(
        self,
        evidence: IdentityShadowFrameEvidence,
    ) -> None:
        session_key = self._identity_session_key
        if session_key is None:
            raise RuntimeError("Identity evidence session is not active.")
        if evidence.session_key != session_key:
            raise ValueError("Identity evidence belongs to another session.")
        next_sequence = self._identity_frame_count + 1
        payload = IdentityShadowEvidenceSerializer.frame_to_dict(
            evidence,
            sequence_number=next_sequence,
            previous_trace=self._identity_previous_trace,
            previous_frame=(self._identity_ring[-1] if self._identity_ring else None),
        )
        frame_key = str(payload["frame_key"])
        if frame_key in self._identity_seen_frame_keys:
            raise ValueError("Duplicate identity frame evidence.")
        event_types = self._identity_event_types(evidence)
        checkpoint_due = self._identity_checkpoint_due(next_sequence)
        if checkpoint_due:
            event_types.append(IdentityShadowEventType.CHECKPOINT)
        png = None
        if self._identity_png_required(event_types):
            png = self._publish_identity_png(evidence)
        payload["png"] = png
        payload["previous_record_sha256"] = self._identity_previous_frame_hash
        record_hash = IdentityShadowEvidenceSerializer.payload_sha256(payload)
        payload["record_sha256"] = record_hash
        self._append_jsonl(self._identity_frames_path, payload)
        self._identity_frame_count = next_sequence
        self._identity_previous_frame_hash = record_hash
        self._identity_seen_frame_keys.add(frame_key)

        previous_status = (
            self._identity_previous_trace.status
            if self._identity_previous_trace is not None
            else None
        )
        try:
            for event_type in event_types:
                self._append_identity_event(
                    event_type=event_type,
                    session_key=session_key,
                    frame_payload=payload,
                    previous_status=(
                        previous_status.value
                        if previous_status is not None
                        else None
                    ),
                    png=png,
                )
        finally:
            self._identity_ring.append(payload)
            self._identity_previous_trace = evidence.resolution.trace

    def _stop_identity_session_locked(self) -> None:
        session_key = self._identity_session_key
        if session_key is None:
            return
        try:
            self._append_identity_event(
                event_type=IdentityShadowEventType.LIFECYCLE_STOP,
                session_key=session_key,
                frame_payload=None,
                previous_status=(
                    self._identity_previous_trace.status.value
                    if self._identity_previous_trace is not None
                    else None
                ),
                png=None,
            )
        except Exception as error:  # noqa: BLE001 - shutdown must be fail-soft.
            self._record_failure_if_possible(
                error=error,
                stage="identity_lifecycle_stop",
                frame_id=(
                    self._identity_previous_trace.frame_id
                    if self._identity_previous_trace is not None
                    else 0
                ),
                snapshot_ids=(),
                relevant_paths=("identity_shadow/events.jsonl",),
            )
        finally:
            self._identity_session_key = None
            self._identity_previous_trace = None
            self._identity_ring.clear()

    def _identity_event_types(
        self,
        evidence: IdentityShadowFrameEvidence,
    ) -> list[IdentityShadowEventType]:
        trace = evidence.resolution.trace
        result = evidence.resolution.result
        previous = self._identity_previous_trace
        events: list[IdentityShadowEventType] = []
        if (
            trace.internal_state is CurrentCandleIdentityLifecycle.BOOTSTRAPPING
            and result.status is not CurrentCandleIdentityStatus.CONFIRMED
            and (
                previous is None
                or previous.diagnostics != trace.diagnostics
                or previous.continuity_generation != trace.continuity_generation
            )
        ):
            events.append(IdentityShadowEventType.BOOTSTRAP_PENDING)
        if result.source is CurrentCandleIdentitySource.BOOTSTRAP_CONFIRMATION:
            events.append(IdentityShadowEventType.BOOTSTRAP_CONFIRMED)
        if trace.rollover_suspected:
            events.append(IdentityShadowEventType.ROLLOVER_SUSPECTED)
        if trace.rollover_confirmed:
            events.append(IdentityShadowEventType.ROLLOVER_CONFIRMED)
        status_changed = previous is None or previous.status is not trace.status
        if status_changed:
            events.append(IdentityShadowEventType.STATUS_CHANGED)
        diagnostic_changed = (
            previous is None
            or previous.diagnostics != trace.diagnostics
            or previous.missing_evidence != trace.missing_evidence
        )
        if (
            trace.status is CurrentCandleIdentityStatus.MISSING_FROM_VIEW
            and (status_changed or diagnostic_changed)
        ):
            events.append(IdentityShadowEventType.MISSING_FROM_VIEW)
        if (
            trace.status is CurrentCandleIdentityStatus.AMBIGUOUS
            and (status_changed or diagnostic_changed)
        ):
            events.append(IdentityShadowEventType.AMBIGUOUS)
        if trace.reset_reason is not None:
            events.append(IdentityShadowEventType.RESET)
        if trace.reset_reason is CurrentCandleIdentityResetReason.INTERNAL_ERROR:
            events.append(IdentityShadowEventType.RESOLVER_FAILURE)
        return list(dict.fromkeys(events))

    def _identity_checkpoint_due(self, sequence_number: int) -> bool:
        assert self._identity_config is not None
        interval = self._identity_config.checkpoint_interval_frames
        return interval is not None and sequence_number % interval == 0

    def _identity_png_required(
        self,
        event_types: list[IdentityShadowEventType],
    ) -> bool:
        assert self._identity_config is not None
        if self._identity_config.png_mode is IdentityShadowPngMode.ALL_FRAMES:
            return True
        relevant = {
            IdentityShadowEventType.ROLLOVER_SUSPECTED,
            IdentityShadowEventType.ROLLOVER_CONFIRMED,
            IdentityShadowEventType.MISSING_FROM_VIEW,
            IdentityShadowEventType.AMBIGUOUS,
            IdentityShadowEventType.RESET,
            IdentityShadowEventType.RESOLVER_FAILURE,
            IdentityShadowEventType.CHECKPOINT,
        }
        return bool(relevant.intersection(event_types))

    def _publish_identity_png(
        self,
        evidence: IdentityShadowFrameEvidence,
    ) -> dict[str, Any]:
        visual_key = IdentityShadowEvidenceSerializer.visual_frame_key(evidence)
        visual_metadata_path = self._frames_directory / visual_key / "frame.json"
        if visual_metadata_path.exists():
            metadata = self._read_json(visual_metadata_path)
            descriptor = metadata.get("images", {}).get("chart")
            if not isinstance(descriptor, dict):
                raise ValueError("Reusable visual evidence has no chart PNG.")
            expected_pixel_hash = self._array_metadata(evidence.image)[
                "pixel_sha256"
            ]
            if descriptor.get("pixel_sha256") != expected_pixel_hash:
                raise ValueError("Reusable visual PNG belongs to different pixels.")
            return {
                "filename": descriptor["filename"],
                "sha256": descriptor["sha256"],
                "pixel_sha256": descriptor["pixel_sha256"],
                "reuses_visual_frame_evidence": True,
            }

        identity_key = IdentityShadowEvidenceSerializer.identity_frame_key(evidence)
        path = self._identity_png_directory / f"{identity_key}.png"
        encoded = self._png_encoder(evidence.image)
        if not isinstance(encoded, bytes) or not encoded:
            raise ValueError("PNG encoder returned no bytes.")
        decoded = cv2.imdecode(
            np.frombuffer(encoded, dtype=np.uint8),
            cv2.IMREAD_UNCHANGED,
        )
        if decoded is None or not np.array_equal(decoded, evidence.image):
            raise ValueError("Identity PNG fidelity validation failed.")
        encoded_hash = hashlib.sha256(encoded).hexdigest()
        if path.exists():
            if hashlib.sha256(path.read_bytes()).hexdigest() != encoded_hash:
                raise ValueError("Conflicting identity PNG already exists.")
        else:
            self._atomic_write_bytes(path, encoded)
        return {
            "filename": path.relative_to(self._directory).as_posix(),
            "sha256": encoded_hash,
            "pixel_sha256": self._array_metadata(evidence.image)["pixel_sha256"],
            "reuses_visual_frame_evidence": False,
        }

    def _append_identity_event(
        self,
        *,
        event_type: IdentityShadowEventType,
        session_key: str,
        frame_payload: dict[str, Any] | None,
        previous_status: str | None,
        png: dict[str, Any] | None,
    ) -> None:
        sequence = self._identity_event_count + 1
        frame_key = frame_payload.get("frame_key") if frame_payload else None
        pre_event_count = (
            self._identity_config.pre_event_trace_count
            if self._identity_config is not None
            else 0
        )
        pre_event_keys = [
            str(item["frame_key"])
            for item in list(self._identity_ring)[-pre_event_count:]
        ] if pre_event_count else []
        payload: dict[str, Any] = {
            "identity_shadow_schema_version": (
                IdentityShadowEvidenceSerializer.SCHEMA_VERSION
            ),
            "sequence_number": sequence,
            "event_id": self._identity_event_id(
                sequence=sequence,
                event_type=event_type,
                session_key=session_key,
                frame_key=str(frame_key) if frame_key is not None else None,
            ),
            "event_type": event_type.value,
            "recorded_at": self._aware_utc_now().isoformat(),
            "session_key": session_key,
            "frame_key": frame_key,
            "frame_id": frame_payload.get("frame_id") if frame_payload else None,
            "wall_timestamp": (
                frame_payload.get("wall_timestamp") if frame_payload else None
            ),
            "continuity_generation": (
                frame_payload.get("continuity_generation")
                if frame_payload
                else None
            ),
            "lifecycle_state": (
                frame_payload.get("lifecycle_state") if frame_payload else None
            ),
            "identity_status": (
                frame_payload.get("identity", {}).get("status")
                if frame_payload
                else None
            ),
            "previous_identity_status": previous_status,
            "reset_reason": (
                frame_payload.get("reset_reason") if frame_payload else None
            ),
            "pre_event_frame_keys": pre_event_keys,
            "png": png,
            "previous_record_sha256": self._identity_previous_event_hash,
        }
        record_hash = IdentityShadowEvidenceSerializer.payload_sha256(payload)
        payload["record_sha256"] = record_hash
        self._append_jsonl(self._identity_events_path, payload)
        self._identity_event_count = sequence
        self._identity_previous_event_hash = record_hash

    @staticmethod
    def _identity_event_id(
        *,
        sequence: int,
        event_type: IdentityShadowEventType,
        session_key: str,
        frame_key: str | None,
    ) -> str:
        session_digest = hashlib.sha256(session_key.encode("utf-8")).hexdigest()[:12]
        target = frame_key or f"session_{session_digest}"
        return f"event_{sequence:08d}_{event_type.value}_{target}"

    def _record_identity_failure(
        self,
        evidence: IdentityShadowFrameEvidence,
        error: Exception,
    ) -> None:
        frame_key = IdentityShadowEvidenceSerializer.identity_frame_key(evidence)
        self._record_failure_if_possible(
            error=error,
            stage="record_identity_shadow",
            frame_id=evidence.frame_id,
            snapshot_ids=(),
            relevant_paths=(
                "identity_shadow/frames.jsonl",
                "identity_shadow/events.jsonl",
                f"identity_shadow/png/{frame_key}.png",
            ),
        )
        try:
            self._append_identity_event(
                event_type=IdentityShadowEventType.PERSISTENCE_FAILURE,
                session_key=evidence.session_key,
                frame_payload={
                    "frame_key": frame_key,
                    "frame_id": evidence.frame_id,
                    "wall_timestamp": evidence.frame_timestamp.isoformat(),
                    "continuity_generation": (
                        evidence.resolution.trace.continuity_generation
                    ),
                    "lifecycle_state": (
                        evidence.resolution.trace.internal_state.value
                    ),
                    "identity": {
                        "status": evidence.resolution.result.status.value
                    },
                    "reset_reason": (
                        evidence.resolution.trace.reset_reason.value
                        if evidence.resolution.trace.reset_reason is not None
                        else None
                    ),
                },
                previous_status=(
                    self._identity_previous_trace.status.value
                    if self._identity_previous_trace is not None
                    else None
                ),
                png=None,
            )
        except Exception:  # noqa: BLE001 - final best-effort failure signal.
            logger.exception("Identity persistence failure event could not be written.")

    def _load_identity_streams(self) -> None:
        reader = IdentityShadowEvidenceReader(self._directory)
        frames = reader.read_frames()
        events = reader.read_events()
        self._identity_frame_count = len(frames)
        self._identity_event_count = len(events)
        self._identity_previous_frame_hash = (
            str(frames[-1]["record_sha256"]) if frames else None
        )
        self._identity_previous_event_hash = (
            str(events[-1]["record_sha256"]) if events else None
        )
        self._identity_seen_frame_keys = {
            str(frame["frame_key"]) for frame in frames
        }

    @classmethod
    def frame_key(cls, frame_evidence: VisualFrameEvidence) -> str:
        timestamp = frame_evidence.frame_timestamp.astimezone(UTC).strftime(
            "%Y%m%dT%H%M%S%fZ"
        )
        return f"frame_{frame_evidence.frame_id:08d}_{timestamp}"

    @staticmethod
    def snapshot_key(snapshot_id: str) -> str:
        digest = hashlib.sha256(snapshot_id.encode("utf-8")).hexdigest()[:12]
        try:
            parsed = datetime.fromisoformat(snapshot_id.replace("Z", "+00:00"))
            if parsed.tzinfo is not None and parsed.utcoffset() is not None:
                parsed = parsed.astimezone(UTC)
                timestamp = parsed.strftime("%Y%m%dT%H%M%S%fZ")
            else:
                timestamp = parsed.strftime("%Y%m%dT%H%M%S%f")
        except ValueError:
            timestamp = re.sub(r"[^A-Za-z0-9_-]", "_", snapshot_id)[:40]
            timestamp = timestamp or "unknown"
        return f"snapshot_{timestamp}_{digest}"

    def _publish_frame(
        self,
        evidence: VisualFrameEvidence,
    ) -> tuple[str, bool, int]:
        frame_key = self.frame_key(evidence)
        known_key = self._frame_keys_by_id.get(evidence.frame_id)
        if known_key is not None and known_key != frame_key:
            raise ValueError(
                "The same frame_id cannot identify different frame timestamps."
            )
        logical_images = self._logical_images(evidence)
        content = {
            "frame_id": evidence.frame_id,
            "frame_timestamp": evidence.frame_timestamp.isoformat(),
            "source": evidence.source,
            "chart_region": VisualEvidenceSerializer.region_to_dict(
                evidence.chart_region,
            ),
            "price_observation_region": VisualEvidenceSerializer.region_to_dict(
                evidence.price_observation_region,
            ),
            "arrays": logical_images,
            "analysis": VisualEvidenceSerializer.analysis_to_dict(evidence),
        }
        fingerprint = self._sha256_json(content)
        final_directory = self._frames_directory / frame_key
        if final_directory.exists():
            metadata = self._read_json(final_directory / "frame.json")
            if (
                metadata.get("frame_key") != frame_key
                or metadata.get("frame_id") != evidence.frame_id
                or metadata.get("content_fingerprint") != fingerprint
            ):
                raise ValueError(
                    "Conflicting evidence already exists for the same frame identity."
                )
            self._validate_persisted_images(metadata)
            self._frame_keys_by_id[evidence.frame_id] = frame_key
            return frame_key, False, 0

        temporary_directory = Path(
            tempfile.mkdtemp(
                prefix=f".tmp_{frame_key}_",
                dir=self._frames_directory,
            )
        )
        try:
            encode_started_at = self._timer()
            chart_descriptor, chart_bytes = self._encode_write_image(
                role="chart",
                image=evidence.image,
                filename="chart.png",
                frame_key=frame_key,
                directory=temporary_directory,
            )
            price_descriptor = None
            total_png_bytes = chart_bytes
            price_image = evidence.price_observation_image
            if price_image is not None:
                if logical_images["price_observation"]["reuses_chart_png"]:
                    price_descriptor = {
                        **chart_descriptor,
                        "role": "price_observation",
                        "reuses_chart_png": True,
                    }
                else:
                    price_descriptor, price_bytes = self._encode_write_image(
                        role="price_observation",
                        image=price_image,
                        filename="price_observation.png",
                        frame_key=frame_key,
                        directory=temporary_directory,
                    )
                    total_png_bytes += price_bytes
            encode_write_duration_ms = (
                self._timer() - encode_started_at
            ) * 1000.0
            metadata = {
                "schema_version": self.SCHEMA_VERSION,
                "frame_key": frame_key,
                "frame_id": evidence.frame_id,
                "frame_timestamp": evidence.frame_timestamp.isoformat(),
                "frame_timestamp_semantics": (
                    "UTC capture timestamp assigned to the analyzed Frame"
                ),
                "source": evidence.source,
                "content_fingerprint": fingerprint,
                "geometry": {
                    "chart_region": content["chart_region"],
                    "price_observation_region": (
                        content["price_observation_region"]
                    ),
                },
                "arrays": logical_images,
                "images": {
                    "chart": chart_descriptor,
                    "price_observation": price_descriptor,
                },
                "analysis": content["analysis"],
                "persistence": {
                    "synchronous": True,
                    "image_encode_write_duration_ms": encode_write_duration_ms,
                },
            }
            self._write_json_file(
                temporary_directory / "frame.json",
                metadata,
            )
            os.replace(temporary_directory, final_directory)
        finally:
            if temporary_directory.exists():
                shutil.rmtree(temporary_directory, ignore_errors=True)
        self._frame_keys_by_id[evidence.frame_id] = frame_key
        return frame_key, True, total_png_bytes

    def _publish_association(
        self,
        *,
        frame_evidence: VisualFrameEvidence,
        frame_key: str,
        snapshot_key: str,
        association: VisualEvidenceAssociation,
    ) -> bool:
        association_key = (association.snapshot_id, association.phase.value)
        directory = self._snapshots_directory / snapshot_key
        path = directory / f"{association.phase.value}.json"
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "snapshot_id": association.snapshot_id,
            "snapshot_key": snapshot_key,
            "phase": association.phase.value,
            "frame_key": frame_key,
            "frame_id": frame_evidence.frame_id,
            "frame_timestamp": frame_evidence.frame_timestamp.isoformat(),
            "observed_at": association.observed_at.isoformat(),
            "candle_interval_started_at": (
                association.candle_interval_started_at.isoformat()
                if association.candle_interval_started_at is not None
                else None
            ),
            "resolve_at": association.resolve_at.isoformat(),
            "resolved_at": (
                association.resolved_at.isoformat()
                if association.resolved_at is not None
                else None
            ),
            "frame_metadata_path": f"frames/{frame_key}/frame.json",
        }
        if path.exists():
            if self._read_json(path) != payload:
                raise ValueError(
                    "Conflicting evidence association already exists for the "
                    "same snapshot and phase."
                )
            if association_key not in self._manifest_associations:
                return True
            return False
        if association_key in self._manifest_associations:
            raise ValueError(
                "Manifest references an evidence association that is missing."
            )
        directory.mkdir(parents=True, exist_ok=True)
        self._atomic_write_json(path, payload)
        return True

    def _logical_images(
        self,
        evidence: VisualFrameEvidence,
    ) -> dict[str, Any]:
        chart = self._array_metadata(evidence.image)
        price_image = evidence.price_observation_image
        price = None
        if price_image is not None:
            reuses_chart = (
                evidence.chart_region == evidence.price_observation_region
                and self._arrays_are_equal(evidence.image, price_image)
            )
            price = {
                **self._array_metadata(price_image),
                "reuses_chart_png": reuses_chart,
            }
        return {
            "chart": {**chart, "reuses_chart_png": False},
            "price_observation": price,
        }

    def _validate_persisted_images(self, metadata: dict[str, Any]) -> None:
        images = metadata.get("images")
        if not isinstance(images, dict):
            raise ValueError("Published frame image metadata is missing.")
        checked_filenames: set[str] = set()
        for descriptor in images.values():
            if descriptor is None:
                continue
            if not isinstance(descriptor, dict):
                raise ValueError("Published frame image descriptor is invalid.")
            filename = descriptor.get("filename")
            expected_digest = descriptor.get("sha256")
            if not isinstance(filename, str) or not isinstance(
                expected_digest,
                str,
            ):
                raise ValueError("Published frame image descriptor is incomplete.")
            if filename in checked_filenames:
                continue
            checked_filenames.add(filename)
            path = self._directory / Path(filename)
            try:
                path.resolve().relative_to(self._directory.resolve())
            except ValueError as error:
                raise ValueError(
                    "Published image path escapes evidence root."
                ) from error
            if not path.is_file():
                raise ValueError("Published frame PNG is missing.")
            actual_digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual_digest != expected_digest:
                raise ValueError("Published frame PNG hash does not match metadata.")

    @staticmethod
    def _array_metadata(image: np.ndarray) -> dict[str, Any]:
        height, width = image.shape[:2]
        channels = image.shape[2] if image.ndim == 3 else 1
        contiguous = np.ascontiguousarray(image)
        pixel_digest = hashlib.sha256(contiguous.tobytes(order="C")).hexdigest()
        return {
            "width": int(width),
            "height": int(height),
            "channels": int(channels),
            "shape": [int(value) for value in image.shape],
            "dtype": str(image.dtype),
            "pixel_sha256": pixel_digest,
        }

    @staticmethod
    def _arrays_are_equal(first: np.ndarray, second: np.ndarray) -> bool:
        return (
            first.shape == second.shape
            and first.dtype == second.dtype
            and np.array_equal(first, second)
        )

    def _encode_write_image(
        self,
        *,
        role: str,
        image: np.ndarray,
        filename: str,
        frame_key: str,
        directory: Path,
    ) -> tuple[dict[str, Any], int]:
        encoded = self._png_encoder(image)
        if not isinstance(encoded, bytes) or not encoded:
            raise ValueError("PNG encoder returned no bytes.")
        decoded = cv2.imdecode(
            np.frombuffer(encoded, dtype=np.uint8),
            cv2.IMREAD_UNCHANGED,
        )
        if decoded is None or not np.array_equal(decoded, image):
            raise ValueError("PNG fidelity validation failed.")
        path = directory / filename
        self._write_bytes_file(path, encoded)
        array_metadata = self._array_metadata(image)
        return (
            {
                "role": role,
                "filename": f"frames/{frame_key}/{filename}",
                "width": array_metadata["width"],
                "height": array_metadata["height"],
                "channels": array_metadata["channels"],
                "dtype": array_metadata["dtype"],
                "sha256": hashlib.sha256(encoded).hexdigest(),
                "pixel_sha256": array_metadata["pixel_sha256"],
                "reuses_chart_png": False,
            },
            len(encoded),
        )

    @staticmethod
    def _default_png_encoder(image: np.ndarray) -> bytes:
        success, encoded = cv2.imencode(".png", image)
        if not success:
            raise ValueError("OpenCV could not encode the visual evidence PNG.")
        return encoded.tobytes()

    def _initialize_session_metadata(self) -> None:
        path = self._directory / "session_metadata.json"
        if path.exists():
            metadata = self._read_json(path)
            if metadata.get("schema_version") != self.SCHEMA_VERSION:
                raise ValueError("Unsupported visual evidence session schema.")
            if self._identity_config is not None:
                expected = self._identity_session_metadata()
                existing = metadata.get("identity_shadow")
                if existing is None:
                    metadata["identity_shadow"] = expected
                    self._atomic_write_json(path, metadata)
                elif existing != expected:
                    raise ValueError(
                        "Identity evidence configuration changed inside one "
                        "evidence session."
                    )
            return
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "created_at": self._aware_utc_now().isoformat(),
            "application_version": self._application_version,
            "source_commit": self._source_commit,
            "opencv_version": cv2.__version__,
            "numpy_version": np.__version__,
            "evidence_directory": ".",
            "observation_jsonl_path": self._portable_observation_path(),
            "image_encoding": {
                "format": "png",
                "lossless": True,
                "encoder": "cv2.imencode",
                "channel_conversion": False,
                "dtype_conversion": False,
            },
            "synchronous_persistence": True,
            "configuration": {
                "deduplicate_frames": True,
                "reuse_identical_price_observation_png": True,
                "association_files_by_snapshot": True,
            },
            "timing_metrics": {
                "image_encode_write_duration_ms": (
                    "PNG encode, fidelity validation and byte writes for a new "
                    "frame package"
                ),
                "record_frame_duration_ms_before_manifest_append": (
                    "elapsed synchronous record_frame time immediately before "
                    "each manifest append"
                ),
            },
            "array_ownership": (
                "borrowed synchronously; async persistence would require copying "
                "or explicit ownership transfer"
            ),
        }
        if self._identity_config is not None:
            payload["identity_shadow"] = self._identity_session_metadata()
        self._atomic_write_json(path, payload)

    def _identity_session_metadata(self) -> dict[str, Any]:
        config = self._identity_config
        if config is None:
            raise RuntimeError("Identity evidence is not configured.")
        return {
            "enabled": True,
            "schema_version": IdentityShadowEvidenceSerializer.SCHEMA_VERSION,
            "frames_stream": "identity_shadow/frames.jsonl",
            "events_stream": "identity_shadow/events.jsonl",
            "ring_buffer_size": config.ring_buffer_size,
            "pre_event_trace_count": config.pre_event_trace_count,
            "png_mode": config.png_mode.value,
            "checkpoint_interval_frames": config.checkpoint_interval_frames,
            "post_event_frames": 0,
            "source_key_persistence": "sha256",
            "thresholds_calibrated": False,
        }

    def _portable_observation_path(self) -> str | None:
        if self._observation_jsonl_path is None:
            return None
        path = Path(self._observation_jsonl_path)
        if not path.is_absolute():
            return path.as_posix()
        try:
            return Path(
                os.path.relpath(path, start=self._directory.resolve())
            ).as_posix()
        except ValueError:
            return path.name

    def _load_existing_frames(self) -> None:
        for directory in self._frames_directory.iterdir():
            if not directory.is_dir() or directory.name.startswith(".tmp_"):
                continue
            metadata_path = directory / "frame.json"
            if not metadata_path.exists():
                raise ValueError("Published frame directory has no frame.json.")
            metadata = self._read_json(metadata_path)
            frame_id = metadata.get("frame_id")
            frame_key = metadata.get("frame_key")
            if not isinstance(frame_id, int) or frame_key != directory.name:
                raise ValueError("Published frame metadata is inconsistent.")
            existing = self._frame_keys_by_id.get(frame_id)
            if existing is not None and existing != frame_key:
                raise ValueError("Duplicate frame_id exists in evidence session.")
            self._frame_keys_by_id[frame_id] = frame_key

    def _load_manifest(self) -> None:
        with self._manifest_path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as error:
                    raise ValueError(
                        f"Invalid manifest JSON at line {line_number}."
                    ) from error
                key = (payload.get("snapshot_id"), payload.get("phase"))
                if not all(isinstance(value, str) for value in key):
                    raise ValueError("Manifest association key is invalid.")
                typed_key = (str(key[0]), str(key[1]))
                if typed_key in self._manifest_associations:
                    raise ValueError("Manifest contains a duplicate association.")
                self._manifest_associations.add(typed_key)

    def _append_manifest(self, payload: dict[str, Any]) -> bool:
        key = (str(payload["snapshot_id"]), str(payload["phase"]))
        if self._manifest_file_contains(key):
            return False
        self._append_jsonl(self._manifest_path, payload)
        return True

    def _manifest_file_contains(self, key: tuple[str, str]) -> bool:
        with self._manifest_path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as error:
                    raise ValueError(
                        f"Invalid manifest JSON at line {line_number}."
                    ) from error
                if (payload.get("snapshot_id"), payload.get("phase")) == key:
                    return True
        return False

    def _record_failure_if_possible(
        self,
        *,
        error: Exception,
        stage: str,
        frame_id: int,
        snapshot_ids: tuple[str, ...],
        relevant_paths: tuple[str, ...],
    ) -> None:
        try:
            self._append_jsonl(
                self._failures_path,
                {
                    "schema_version": self.SCHEMA_VERSION,
                    "timestamp": self._aware_utc_now().isoformat(),
                    "frame_id": frame_id,
                    "snapshot_ids": list(snapshot_ids),
                    "stage": stage,
                    "exception_type": type(error).__name__,
                    "message": str(error),
                    "paths": list(relevant_paths),
                },
            )
        except Exception:
            logger.exception("Visual evidence failure log could not be written.")

    @staticmethod
    def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            json.dump(
                FilesystemVisualEvidenceRecorder._json_native(payload),
                stream,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())

    @staticmethod
    def _ensure_append_file(path: Path) -> None:
        with path.open("a", encoding="utf-8") as stream:
            stream.flush()

    @staticmethod
    def _write_bytes_file(path: Path, payload: bytes) -> None:
        with path.open("wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())

    @staticmethod
    def _atomic_write_bytes(path: Path, payload: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_path, path)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

    @classmethod
    def _write_json_file(cls, path: Path, payload: dict[str, Any]) -> None:
        with path.open("w", encoding="utf-8", newline="\n") as stream:
            cls._dump_json(payload, stream)
            stream.flush()
            os.fsync(stream.fileno())

    @classmethod
    def _atomic_write_json(cls, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(
                descriptor,
                "w",
                encoding="utf-8",
                newline="\n",
            ) as stream:
                cls._dump_json(payload, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_path, path)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

    @staticmethod
    def _dump_json(payload: dict[str, Any], stream: Any) -> None:
        json.dump(
            FilesystemVisualEvidenceRecorder._json_native(payload),
            stream,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        stream.write("\n")

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as stream:
            payload = json.load(stream)
        if not isinstance(payload, dict):
            raise ValueError(f"Expected JSON object in {path.name}.")
        return payload

    @staticmethod
    def _sha256_json(payload: dict[str, Any]) -> str:
        encoded = json.dumps(
            FilesystemVisualEvidenceRecorder._json_native(payload),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _json_native(value: Any) -> Any:
        if isinstance(value, np.ndarray):
            raise TypeError("ndarrays must be persisted as PNG, never JSON.")
        if isinstance(value, np.generic):
            return value.item()
        if isinstance(value, dict):
            return {
                str(key): FilesystemVisualEvidenceRecorder._json_native(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [
                FilesystemVisualEvidenceRecorder._json_native(item)
                for item in value
            ]
        return value

    def _aware_utc_now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Evidence clock must return a timezone-aware datetime.")
        return value.astimezone(UTC)
