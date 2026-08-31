"""Harness experimental para adquirir bursts físicos de precio visual.

Este módulo no forma parte del runtime productivo. Durante la sección
temporal crítica sólo programa deadlines, captura frames independientes y
retiene sus referencias en memoria. El análisis y la persistencia se ejecutan
después de completar cada burst.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, fields, is_dataclass
from datetime import UTC, datetime
from enum import Enum, StrEnum
from hashlib import sha256
from math import ceil, isfinite
from pathlib import Path
from statistics import median
from typing import Any, Protocol, cast
from uuid import uuid4

import cv2
import numpy as np

from pocket_option_analyzer.infrastructure.bootstrap import (
    PocketOptionRuntimeFactory,
)
from pocket_option_analyzer.infrastructure.capture.models import Frame
from pocket_option_analyzer.vision.models import (
    CurrentVisualPriceAnalysis,
    CurrentVisualPriceDetectionTrace,
)
from pocket_option_analyzer.vision.services import (
    PocketOptionCurrentVisualPriceExtractor,
    PocketOptionCurrentVisualPriceSearchWindowResolver,
)

_NANOSECONDS_PER_SECOND = 1_000_000_000
_COMMIT_PATTERN = re.compile(r"^[0-9a-fA-F]{40}$")


class CalibrationHarnessError(RuntimeError):
    """Error fail-closed del harness de calibración."""


class TechnicalFailureReason(StrEnum):
    """Razones técnicas; nunca clasifican movimiento ni estacionariedad."""

    CAPTURE_UNAVAILABLE = "capture_unavailable"
    CAPTURE_ERROR = "capture_error"
    SOURCE_CHANGED = "source_changed"
    GEOMETRY_CHANGED = "geometry_changed"
    NON_MONOTONIC_TIMESTAMP = "non_monotonic_timestamp"
    DEADLINE_OVERRUN = "deadline_overrun"
    FRAME_MEMORY_REUSED = "frame_memory_reused"
    PNG_ROUNDTRIP_FAILED = "png_roundtrip_failed"
    EXTRACTOR_ERROR = "extractor_error"
    PERSISTENCE_ERROR = "persistence_error"
    INCOMPLETE = "incomplete"
    INTERRUPTED = "interrupted"


class BurstTechnicalStatus(StrEnum):
    """Estado exclusivamente técnico de un candidate burst."""

    VALID_TECHNICAL = "valid_technical"
    INVALID_TECHNICAL = "invalid_technical"
    INCOMPLETE = "incomplete"


class FrameCaptureService(Protocol):
    """Puerto mínimo de captura reutilizado por el harness."""

    def capture_once(self) -> Frame | None:
        """Realiza una captura física independiente."""


class VisualPriceTraceExtractor(Protocol):
    """Contrato de la variante productiva que expone extracción y trace."""

    def extract_with_trace(self, image: np.ndarray) -> CurrentVisualPriceAnalysis:
        """Extrae CurrentVisualPrice sin modificar los píxeles recibidos."""


class GitProvenanceProvider(Protocol):
    """Obtiene provenance del checkout que ejecuta la campaña."""

    def resolve(self, repository_root: Path, remote: str) -> GitProvenance:
        """Devuelve HEAD, rama, limpieza y tracking cuando está disponible."""


@dataclass(frozen=True, slots=True)
class GitProvenance:
    """Estado Git persistido de forma explícita en la sesión."""

    branch: str
    head: str
    dirty: bool
    ahead: int | None
    behind: int | None
    remote: str
    tracking_diagnostic: str | None = None


@dataclass(frozen=True, slots=True)
class HarnessConfig:
    """Parámetros de ejecución, ajenos a pixel_tolerance."""

    frames_per_burst: int = 5
    target_fps: float = 8.0
    candidate_bursts: int = 20
    preflight_frames: int = 30
    inter_burst_delay_seconds: float = 0.0

    def __post_init__(self) -> None:
        if not 5 <= self.frames_per_burst <= 10:
            raise ValueError("frames_per_burst debe estar entre 5 y 10.")
        if self.candidate_bursts < 1:
            raise ValueError("candidate_bursts debe ser mayor que cero.")
        if self.preflight_frames < 5:
            raise ValueError("preflight_frames debe ser al menos 5.")
        if not isfinite(self.target_fps) or self.target_fps <= 0.0:
            raise ValueError("target_fps debe ser finito y positivo.")
        if (
            not isfinite(self.inter_burst_delay_seconds)
            or self.inter_burst_delay_seconds < 0.0
        ):
            raise ValueError("inter_burst_delay_seconds no puede ser negativo.")

    @property
    def period_ns(self) -> int:
        """Período nominal redondeado a nanosegundos."""

        period = round(_NANOSECONDS_PER_SECOND / self.target_fps)
        if period < 1:
            raise ValueError("target_fps produce un período inferior a 1 ns.")
        return period


@dataclass(frozen=True, slots=True)
class CapturedSlot:
    """Intento de captura retenido sin procesamiento durante el burst."""

    sequence_in_batch: int
    deadline_ns: int
    capture_started_ns: int
    capture_completed_ns: int
    frame: Frame | None
    capture_error: str | None = None

    @property
    def lateness_ns(self) -> int:
        """Retraso real del inicio respecto del deadline absoluto."""

        return max(0, self.capture_started_ns - self.deadline_ns)


@dataclass(frozen=True, slots=True)
class CaptureBatch:
    """Resultado crudo de una sección temporal crítica."""

    started_ns: int
    completed_ns: int
    requested_count: int
    slots: tuple[CapturedSlot, ...]
    interrupted: bool


@dataclass(frozen=True, slots=True)
class _PreflightSlot:
    sequence: int
    deadline_ns: int
    capture_started_ns: int
    capture_completed_ns: int
    frame_available: bool
    capture_error: str | None

    @property
    def lateness_ns(self) -> int:
        return max(0, self.capture_started_ns - self.deadline_ns)


@dataclass(frozen=True, slots=True)
class _PreflightBatch:
    started_ns: int
    completed_ns: int
    requested_count: int
    slots: tuple[_PreflightSlot, ...]
    interrupted: bool


@dataclass(frozen=True, slots=True)
class CalibrationSessionResult:
    """Resumen final devuelto al CLI."""

    session_id: str
    output_directory: Path
    captured_bursts: int
    valid_technical_bursts: int
    interrupted: bool
    source_commit: str


@dataclass(frozen=True, slots=True)
class _ImageDescriptor:
    role: str
    filename: str
    pixel_sha256: str
    png_sha256: str
    shape: tuple[int, ...]
    dtype: str
    channel_count: int
    reuses_current_visual_price_png: bool


class SystemGitProvenanceProvider:
    """Proveedor Git real usado por una ejecución formal."""

    def resolve(self, repository_root: Path, remote: str) -> GitProvenance:
        branch = self._git(repository_root, "branch", "--show-current")
        head = self._git(repository_root, "rev-parse", "HEAD")
        dirty = bool(self._git(repository_root, "status", "--porcelain"))
        ahead: int | None = None
        behind: int | None = None
        tracking_diagnostic: str | None = None
        try:
            divergence = self._git(
                repository_root,
                "rev-list",
                "--left-right",
                "--count",
                f"HEAD...{remote}/{branch}",
            )
            ahead_text, behind_text = divergence.split()
            ahead = int(ahead_text)
            behind = int(behind_text)
        except (CalibrationHarnessError, ValueError) as error:
            tracking_diagnostic = str(error)
        return GitProvenance(
            branch=branch,
            head=head,
            dirty=dirty,
            ahead=ahead,
            behind=behind,
            remote=remote,
            tracking_diagnostic=tracking_diagnostic,
        )

    @staticmethod
    def _git(repository_root: Path, *arguments: str) -> str:
        try:
            completed = subprocess.run(
                ("git", *arguments),
                cwd=repository_root,
                check=True,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError) as error:
            raise CalibrationHarnessError(
                f"No se pudo resolver provenance Git: git {' '.join(arguments)}"
            ) from error
        return completed.stdout.strip()


class _SessionStore:
    """Persistencia post-burst, deliberadamente fuera de la sección crítica."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self.bursts_path = directory / "bursts.jsonl"
        self.frames_path = directory / "frames.jsonl"
        self.failures_path = directory / "failures.jsonl"
        for path in (self.bursts_path, self.frames_path, self.failures_path):
            self._atomic_write_bytes(path, b"")

    def write_json(self, filename: str, payload: Mapping[str, Any]) -> None:
        encoded = self._json_bytes(payload, pretty=True)
        self._atomic_write_bytes(self.directory / filename, encoded)

    def append_jsonl(self, path: Path, payload: Mapping[str, Any]) -> None:
        encoded = self._json_bytes(payload, pretty=False) + b"\n"
        with path.open("ab") as output:
            output.write(encoded)
            output.flush()
            os.fsync(output.fileno())

    def publish_lossless_png(
        self,
        *,
        relative_path: Path,
        encoded: bytes,
        expected_image: np.ndarray,
    ) -> None:
        """Escribe a temporal, verifica el round-trip y sólo entonces publica."""

        path = self.directory / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            with temporary.open("xb") as output:
                output.write(encoded)
                output.flush()
                os.fsync(output.fileno())
            persisted = temporary.read_bytes()
            decoded = cv2.imdecode(
                np.frombuffer(persisted, dtype=np.uint8),
                cv2.IMREAD_UNCHANGED,
            )
            if (
                decoded is None
                or decoded.shape != expected_image.shape
                or decoded.dtype != expected_image.dtype
                or not np.array_equal(decoded, expected_image)
            ):
                raise ValueError(
                    "El round-trip PNG no preservó exactamente el ndarray."
                )
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()

    def record_failure(
        self,
        *,
        session_id: str,
        reason: TechnicalFailureReason,
        diagnostic: str,
        burst_id: str | None = None,
        frame_sequence: int | None = None,
    ) -> None:
        self.append_jsonl(
            self.failures_path,
            {
                "schema_version": 1,
                "session_id": session_id,
                "burst_id": burst_id,
                "frame_sequence": frame_sequence,
                "reason": reason.value,
                "diagnostic": diagnostic,
            },
        )

    @staticmethod
    def _json_bytes(payload: Mapping[str, Any], *, pretty: bool) -> bytes:
        indent = 2 if pretty else None
        return json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            indent=indent,
            separators=None if pretty else (",", ":"),
        ).encode("utf-8")

    @staticmethod
    def _atomic_write_bytes(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            with temporary.open("xb") as output:
                output.write(content)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()


class CurrentVisualPriceBurstHarness:
    """Adquiere candidate bursts sin clasificarlos como S0/S1/M."""

    SCHEMA_VERSION = 1

    def __init__(
        self,
        *,
        capture_service: FrameCaptureService,
        extractor: VisualPriceTraceExtractor,
        git_provider: GitProvenanceProvider | None = None,
        monotonic_clock_ns: Callable[[], int] | None = None,
        wall_clock: Callable[[], datetime] | None = None,
        sleeper: Callable[[float], None] | None = None,
        png_encoder: Callable[[np.ndarray], bytes] | None = None,
        session_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._capture_service = capture_service
        self._extractor = extractor
        self._git_provider = git_provider or SystemGitProvenanceProvider()
        self._monotonic_clock_ns = monotonic_clock_ns or time.monotonic_ns
        self._wall_clock = wall_clock or (lambda: datetime.now(UTC))
        self._sleeper = sleeper or time.sleep
        self._png_encoder = png_encoder or self._encode_png
        self._session_id_factory = session_id_factory or self._default_session_id

    def run(
        self,
        *,
        config: HarnessConfig,
        output_directory: Path,
        repository_root: Path,
        expected_commit: str,
        remote: str = "origin",
    ) -> CalibrationSessionResult:
        """Ejecuta preflight y candidate bursts con provenance fail-closed."""

        resolved_repository = repository_root.resolve()
        resolved_output = validate_external_output_directory(
            output_directory=output_directory,
            repository_root=resolved_repository,
        )
        provenance = self._verified_provenance(
            repository_root=resolved_repository,
            expected_commit=expected_commit,
            remote=remote,
        )
        session_id = self._session_id_factory()
        if not session_id:
            raise CalibrationHarnessError("session_id no puede estar vacío.")
        store = _SessionStore(resolved_output)
        started_at = self._aware_wall_now()
        metadata = self._session_metadata(
            session_id=session_id,
            config=config,
            provenance=provenance,
            expected_commit=expected_commit,
            started_at=started_at,
            status="running",
        )
        store.write_json("session_metadata.json", metadata)

        interrupted = False
        burst_count = 0
        valid_count = 0
        global_frame_sequence = 0
        try:
            preflight = self._capture_preflight(
                frame_count=config.preflight_frames,
                period_ns=config.period_ns,
            )
            interrupted = preflight.interrupted
            store.write_json(
                "preflight.json",
                self._preflight_payload(preflight, config),
            )
            preflight_interrupted = preflight.interrupted
            del preflight
            interrupted = preflight_interrupted
            if preflight_interrupted:
                store.record_failure(
                    session_id=session_id,
                    reason=TechnicalFailureReason.INTERRUPTED,
                    diagnostic="La interrupción ocurrió durante el preflight.",
                )

            for burst_sequence in range(1, config.candidate_bursts + 1):
                if interrupted:
                    break
                burst_id = f"{session_id}_burst_{burst_sequence:04d}"
                batch = self.capture_batch(
                    frame_count=config.frames_per_burst,
                    period_ns=config.period_ns,
                )
                burst_count += 1
                payload, frame_payloads, reasons = self._process_burst(
                    store=store,
                    session_id=session_id,
                    burst_id=burst_id,
                    burst_sequence=burst_sequence,
                    global_frame_sequence=global_frame_sequence,
                    batch=batch,
                    config=config,
                )
                global_frame_sequence += len(batch.slots)
                for frame_payload in frame_payloads:
                    try:
                        store.append_jsonl(store.frames_path, frame_payload)
                    except OSError as error:
                        reasons.add(TechnicalFailureReason.PERSISTENCE_ERROR)
                        store.record_failure(
                            session_id=session_id,
                            burst_id=burst_id,
                            frame_sequence=cast(
                                int,
                                frame_payload["global_frame_sequence"],
                            ),
                            reason=TechnicalFailureReason.PERSISTENCE_ERROR,
                            diagnostic=f"frames.jsonl: {error}",
                        )
                status = self._technical_status(batch, reasons)
                payload["technical_status"] = status.value
                payload["technical_failure_reasons"] = sorted(
                    reason.value for reason in reasons
                )
                capture_complete = (
                    len(batch.slots) == batch.requested_count
                    and all(slot.frame is not None for slot in batch.slots)
                    and not batch.interrupted
                )
                evidence_incomplete_reasons = {
                    TechnicalFailureReason.PNG_ROUNDTRIP_FAILED,
                    TechnicalFailureReason.EXTRACTOR_ERROR,
                    TechnicalFailureReason.PERSISTENCE_ERROR,
                }
                payload["capture_complete"] = capture_complete
                payload["evidence_complete"] = capture_complete and not (
                    reasons & evidence_incomplete_reasons
                )
                payload["complete"] = payload["evidence_complete"]
                if status is BurstTechnicalStatus.VALID_TECHNICAL:
                    valid_count += 1
                store.append_jsonl(store.bursts_path, payload)
                for reason in sorted(reasons, key=lambda item: item.value):
                    store.record_failure(
                        session_id=session_id,
                        burst_id=burst_id,
                        reason=reason,
                        diagnostic="Candidate burst técnicamente inválido.",
                    )
                if batch.interrupted:
                    interrupted = True
                    break
                if (
                    burst_sequence < config.candidate_bursts
                    and config.inter_burst_delay_seconds > 0.0
                ):
                    try:
                        self._sleeper(config.inter_burst_delay_seconds)
                    except KeyboardInterrupt:
                        interrupted = True
                        store.record_failure(
                            session_id=session_id,
                            reason=TechnicalFailureReason.INTERRUPTED,
                            diagnostic="Interrupción entre candidate bursts.",
                        )
                        break
        except Exception as error:
            metadata = {
                **metadata,
                "status": "failed",
                "completed_at": self._aware_wall_now().isoformat(),
                "fatal_error": f"{type(error).__name__}: {error}",
            }
            store.write_json("session_metadata.json", metadata)
            raise

        final_status = "interrupted" if interrupted else "completed"
        completed_at = self._aware_wall_now()
        summary = {
            "schema_version": self.SCHEMA_VERSION,
            "session_id": session_id,
            "status": final_status,
            "candidate_bursts_captured": burst_count,
            "valid_technical_bursts": valid_count,
            "ground_truth_classification": None,
            "candidate_bursts_are_not_accepted_stationary_bursts": True,
            "completed_at": completed_at.isoformat(),
        }
        store.write_json("summary.json", summary)
        store.write_json(
            "session_metadata.json",
            {
                **metadata,
                "status": final_status,
                "completed_at": completed_at.isoformat(),
            },
        )
        return CalibrationSessionResult(
            session_id=session_id,
            output_directory=resolved_output,
            captured_bursts=burst_count,
            valid_technical_bursts=valid_count,
            interrupted=interrupted,
            source_commit=provenance.head,
        )

    def capture_batch(self, *, frame_count: int, period_ns: int) -> CaptureBatch:
        """Sección crítica: captura solamente, sin análisis ni persistencia."""

        started_ns = self._monotonic_clock_ns()
        slots: list[CapturedSlot] = []
        interrupted = False
        for sequence in range(1, frame_count + 1):
            deadline_ns = started_ns + (sequence - 1) * period_ns
            try:
                self._wait_until(deadline_ns)
                capture_started_ns = self._monotonic_clock_ns()
                try:
                    frame = self._capture_service.capture_once()
                    capture_error = None
                except KeyboardInterrupt:
                    interrupted = True
                    break
                except Exception as error:  # noqa: BLE001 - diagnostic capture.
                    frame = None
                    capture_error = f"{type(error).__name__}: {error}"
                capture_completed_ns = self._monotonic_clock_ns()
            except KeyboardInterrupt:
                interrupted = True
                break
            slots.append(
                CapturedSlot(
                    sequence_in_batch=sequence,
                    deadline_ns=deadline_ns,
                    capture_started_ns=capture_started_ns,
                    capture_completed_ns=capture_completed_ns,
                    frame=frame,
                    capture_error=capture_error,
                )
            )
        return CaptureBatch(
            started_ns=started_ns,
            completed_ns=self._monotonic_clock_ns(),
            requested_count=frame_count,
            slots=tuple(slots),
            interrupted=interrupted,
        )

    def _capture_preflight(
        self,
        *,
        frame_count: int,
        period_ns: int,
    ) -> _PreflightBatch:
        """Mide capture-only conservando sólo metadata ligera por intento."""

        started_ns = self._monotonic_clock_ns()
        slots: list[_PreflightSlot] = []
        interrupted = False
        for sequence in range(1, frame_count + 1):
            deadline_ns = started_ns + (sequence - 1) * period_ns
            try:
                self._wait_until(deadline_ns)
                capture_started_ns = self._monotonic_clock_ns()
                try:
                    frame_available = self._capture_service.capture_once() is not None
                    capture_error = None
                except KeyboardInterrupt:
                    interrupted = True
                    break
                except Exception as error:  # noqa: BLE001 - diagnostic preflight.
                    frame_available = False
                    capture_error = f"{type(error).__name__}: {error}"
                capture_completed_ns = self._monotonic_clock_ns()
            except KeyboardInterrupt:
                interrupted = True
                break
            slots.append(
                _PreflightSlot(
                    sequence=sequence,
                    deadline_ns=deadline_ns,
                    capture_started_ns=capture_started_ns,
                    capture_completed_ns=capture_completed_ns,
                    frame_available=frame_available,
                    capture_error=capture_error,
                )
            )
        return _PreflightBatch(
            started_ns=started_ns,
            completed_ns=self._monotonic_clock_ns(),
            requested_count=frame_count,
            slots=tuple(slots),
            interrupted=interrupted,
        )

    def _wait_until(self, deadline_ns: int) -> None:
        while True:
            remaining_ns = deadline_ns - self._monotonic_clock_ns()
            if remaining_ns <= 0:
                return
            self._sleeper(remaining_ns / _NANOSECONDS_PER_SECOND)

    def _process_burst(
        self,
        *,
        store: _SessionStore,
        session_id: str,
        burst_id: str,
        burst_sequence: int,
        global_frame_sequence: int,
        batch: CaptureBatch,
        config: HarnessConfig,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], set[TechnicalFailureReason]]:
        reasons = self._batch_failure_reasons(batch, config.period_ns)
        frame_payloads: list[dict[str, Any]] = []
        for offset, slot in enumerate(batch.slots, start=1):
            sequence = global_frame_sequence + offset
            payload, frame_reasons = self._process_frame(
                store=store,
                session_id=session_id,
                burst_id=burst_id,
                burst_sequence=burst_sequence,
                global_frame_sequence=sequence,
                slot=slot,
            )
            reasons.update(frame_reasons)
            frame_payloads.append(payload)
        status = self._technical_status(batch, reasons)
        for payload in frame_payloads:
            payload["burst_technical_status"] = status.value
        return (
            {
                "schema_version": self.SCHEMA_VERSION,
                "session_id": session_id,
                "burst_id": burst_id,
                "burst_sequence": burst_sequence,
                "candidate_only": True,
                "ground_truth_classification": None,
                "requested_frame_count": batch.requested_count,
                "captured_slot_count": len(batch.slots),
                "physical_capture_count": sum(
                    slot.frame is not None for slot in batch.slots
                ),
                "started_monotonic_ns": batch.started_ns,
                "completed_monotonic_ns": batch.completed_ns,
                "target_fps": config.target_fps,
                "period_ns": config.period_ns,
                "interrupted": batch.interrupted,
                "frame_sequences": [
                    cast(int, payload["global_frame_sequence"])
                    for payload in frame_payloads
                ],
            },
            frame_payloads,
            reasons,
        )

    def _process_frame(
        self,
        *,
        store: _SessionStore,
        session_id: str,
        burst_id: str,
        burst_sequence: int,
        global_frame_sequence: int,
        slot: CapturedSlot,
    ) -> tuple[dict[str, Any], set[TechnicalFailureReason]]:
        reasons: set[TechnicalFailureReason] = set()
        base: dict[str, Any] = {
            "schema_version": self.SCHEMA_VERSION,
            "session_id": session_id,
            "burst_id": burst_id,
            "burst_sequence": burst_sequence,
            "sequence_in_burst": slot.sequence_in_batch,
            "global_frame_sequence": global_frame_sequence,
            "deadline_monotonic_ns": slot.deadline_ns,
            "capture_started_monotonic_ns": slot.capture_started_ns,
            "capture_completed_monotonic_ns": slot.capture_completed_ns,
            "lateness_ns": slot.lateness_ns,
            "capture_error": slot.capture_error,
            "ground_truth_classification": None,
        }
        frame = slot.frame
        if frame is None:
            reason = (
                TechnicalFailureReason.CAPTURE_ERROR
                if slot.capture_error is not None
                else TechnicalFailureReason.CAPTURE_UNAVAILABLE
            )
            reasons.add(reason)
            return (
                {
                    **base,
                    "frame_id": None,
                    "observed_wall_timestamp": None,
                    "observed_monotonic_ns": None,
                    "source_key": None,
                    "geometry": None,
                    "images": None,
                    "current_visual_price": None,
                },
                reasons,
            )

        cvp_image = (
            frame.price_observation_image
            if frame.price_observation_image is not None
            else frame.image
        )
        frame_directory = (
            Path("bursts")
            / burst_id
            / "frames"
            / f"frame_{global_frame_sequence:06d}"
        )
        image_payload: dict[str, Any] | None = None
        try:
            cvp_descriptor = self._persist_image(
                store=store,
                role="current_visual_price_input",
                relative_path=frame_directory / "current_visual_price.png",
                image=cvp_image,
                reuses_current_visual_price_png=False,
            )
            if self._arrays_are_equal(frame.image, cvp_image):
                chart_descriptor = _ImageDescriptor(
                    role="chart",
                    filename=cvp_descriptor.filename,
                    pixel_sha256=cvp_descriptor.pixel_sha256,
                    png_sha256=cvp_descriptor.png_sha256,
                    shape=cvp_descriptor.shape,
                    dtype=cvp_descriptor.dtype,
                    channel_count=cvp_descriptor.channel_count,
                    reuses_current_visual_price_png=True,
                )
            else:
                chart_descriptor = self._persist_image(
                    store=store,
                    role="chart",
                    relative_path=frame_directory / "chart.png",
                    image=frame.image,
                    reuses_current_visual_price_png=False,
                )
            image_payload = {
                "current_visual_price_input": _json_value(cvp_descriptor),
                "chart": _json_value(chart_descriptor),
                "price_observation_relation": (
                    "explicit_price_observation"
                    if frame.price_observation_image is not None
                    else "fallback_to_chart"
                ),
            }
        except (OSError, ValueError, cv2.error) as error:
            image_failure_reason = (
                TechnicalFailureReason.PERSISTENCE_ERROR
                if isinstance(error, OSError)
                else TechnicalFailureReason.PNG_ROUNDTRIP_FAILED
            )
            reasons.add(image_failure_reason)
            try:
                store.record_failure(
                    session_id=session_id,
                    burst_id=burst_id,
                    frame_sequence=global_frame_sequence,
                    reason=image_failure_reason,
                    diagnostic=f"{type(error).__name__}: {error}",
                )
            except OSError:
                reasons.add(TechnicalFailureReason.PERSISTENCE_ERROR)

        extraction_payload: dict[str, Any] | None = None
        try:
            analysis = self._extractor.extract_with_trace(cvp_image)
            extraction_payload = self._analysis_payload(analysis)
        except Exception as error:  # noqa: BLE001 - evidence must diagnose it.
            reasons.add(TechnicalFailureReason.EXTRACTOR_ERROR)
            try:
                store.record_failure(
                    session_id=session_id,
                    burst_id=burst_id,
                    frame_sequence=global_frame_sequence,
                    reason=TechnicalFailureReason.EXTRACTOR_ERROR,
                    diagnostic=f"{type(error).__name__}: {error}",
                )
            except OSError:
                reasons.add(TechnicalFailureReason.PERSISTENCE_ERROR)

        return (
            {
                **base,
                "frame_id": frame.frame_id,
                "observed_wall_timestamp": frame.timestamp.isoformat(),
                "observed_monotonic_ns": frame.monotonic_timestamp_ns,
                "source_key": frame.source_key,
                "geometry": self._geometry_payload(frame),
                "images": image_payload,
                "current_visual_price": extraction_payload,
            },
            reasons,
        )

    def _persist_image(
        self,
        *,
        store: _SessionStore,
        role: str,
        relative_path: Path,
        image: np.ndarray,
        reuses_current_visual_price_png: bool,
    ) -> _ImageDescriptor:
        encoded = self._png_encoder(image)
        if not isinstance(encoded, bytes) or not encoded:
            raise ValueError("El encoder PNG no devolvió bytes.")
        store.publish_lossless_png(
            relative_path=relative_path,
            encoded=encoded,
            expected_image=image,
        )
        channel_count = int(image.shape[2]) if image.ndim == 3 else 1
        return _ImageDescriptor(
            role=role,
            filename=relative_path.as_posix(),
            pixel_sha256=_pixel_sha256(image),
            png_sha256=sha256(encoded).hexdigest(),
            shape=tuple(int(value) for value in image.shape),
            dtype=str(image.dtype),
            channel_count=channel_count,
            reuses_current_visual_price_png=reuses_current_visual_price_png,
        )

    def _batch_failure_reasons(
        self,
        batch: CaptureBatch,
        period_ns: int,
    ) -> set[TechnicalFailureReason]:
        reasons: set[TechnicalFailureReason] = set()
        if batch.interrupted:
            reasons.update(
                {
                    TechnicalFailureReason.INTERRUPTED,
                    TechnicalFailureReason.INCOMPLETE,
                }
            )
        if len(batch.slots) != batch.requested_count:
            reasons.add(TechnicalFailureReason.INCOMPLETE)
        unavailable = any(
            slot.frame is None and slot.capture_error is None for slot in batch.slots
        )
        if unavailable:
            reasons.add(TechnicalFailureReason.CAPTURE_UNAVAILABLE)
        if any(slot.frame is None for slot in batch.slots):
            reasons.add(TechnicalFailureReason.INCOMPLETE)
        if any(slot.capture_error is not None for slot in batch.slots):
            reasons.add(TechnicalFailureReason.CAPTURE_ERROR)
        if any(slot.lateness_ns >= period_ns for slot in batch.slots):
            reasons.add(TechnicalFailureReason.DEADLINE_OVERRUN)

        frames = tuple(
            cast(Frame, slot.frame) for slot in batch.slots if slot.frame is not None
        )
        if frames:
            sources = {frame.source_key for frame in frames}
            if None in sources or len(sources) != 1:
                reasons.add(TechnicalFailureReason.SOURCE_CHANGED)
            geometries = {self._geometry_signature(frame) for frame in frames}
            if len(geometries) != 1:
                reasons.add(TechnicalFailureReason.GEOMETRY_CHANGED)
            timestamps = [frame.monotonic_timestamp_ns for frame in frames]
            if any(timestamp is None for timestamp in timestamps) or any(
                cast(int, right) <= cast(int, left)
                for left, right in zip(timestamps, timestamps[1:], strict=False)
            ):
                reasons.add(TechnicalFailureReason.NON_MONOTONIC_TIMESTAMP)
            if self._memory_is_reused(frames):
                reasons.add(TechnicalFailureReason.FRAME_MEMORY_REUSED)
        return reasons

    @staticmethod
    def _memory_is_reused(frames: Sequence[Frame]) -> bool:
        if len({id(frame) for frame in frames}) != len(frames):
            return True
        images: list[np.ndarray] = []
        for frame in frames:
            images.append(frame.image)
            if frame.price_observation_image is not None:
                images.append(frame.price_observation_image)
        for index, image in enumerate(images):
            for other in images[index + 1 :]:
                if np.shares_memory(image, other):
                    return True
        return False

    @staticmethod
    def _technical_status(
        batch: CaptureBatch,
        reasons: set[TechnicalFailureReason],
    ) -> BurstTechnicalStatus:
        if (
            batch.interrupted
            or TechnicalFailureReason.INCOMPLETE in reasons
            or len(batch.slots) != batch.requested_count
        ):
            return BurstTechnicalStatus.INCOMPLETE
        if reasons:
            return BurstTechnicalStatus.INVALID_TECHNICAL
        return BurstTechnicalStatus.VALID_TECHNICAL

    def _preflight_payload(
        self,
        batch: _PreflightBatch,
        config: HarnessConfig,
    ) -> dict[str, Any]:
        starts = [slot.capture_started_ns for slot in batch.slots]
        spacings = [
            right - left for left, right in zip(starts, starts[1:], strict=False)
        ]
        five_frame_spans = [
            starts[index + 4] - starts[index]
            for index in range(max(0, len(starts) - 4))
        ]
        elapsed_ns = starts[-1] - starts[0] if len(starts) > 1 else 0
        effective_fps = (
            (len(starts) - 1) * _NANOSECONDS_PER_SECOND / elapsed_ns
            if elapsed_ns > 0
            else None
        )
        return {
            "schema_version": self.SCHEMA_VERSION,
            "measurement_only": True,
            "campaign_acceptance_policy_applied": False,
            "requested_frames": batch.requested_count,
            "attempted_frames": len(batch.slots),
            "available_frames": sum(slot.frame_available for slot in batch.slots),
            "capture_errors": sum(
                slot.capture_error is not None for slot in batch.slots
            ),
            "elapsed_ns": elapsed_ns,
            "effective_fps": effective_fps,
            "target_fps": config.target_fps,
            "period_ns": config.period_ns,
            "spacing_ns": self._distribution(spacings),
            "five_frame_span_ns": self._distribution(five_frame_spans),
            "missed_deadlines": sum(
                slot.lateness_ns >= config.period_ns for slot in batch.slots
            ),
            "max_lateness_ns": max(
                (slot.lateness_ns for slot in batch.slots),
                default=None,
            ),
            "interrupted": batch.interrupted,
        }

    @staticmethod
    def _distribution(values: Sequence[int]) -> dict[str, float | int] | None:
        if not values:
            return None
        ordered = sorted(values)
        return {
            "count": len(ordered),
            "minimum": ordered[0],
            "median": median(ordered),
            "p95": _percentile(ordered, 0.95),
            "maximum": ordered[-1],
        }

    def _verified_provenance(
        self,
        *,
        repository_root: Path,
        expected_commit: str,
        remote: str,
    ) -> GitProvenance:
        if not _COMMIT_PATTERN.fullmatch(expected_commit):
            raise CalibrationHarnessError(
                "expected_commit debe ser un SHA-1 Git completo de 40 caracteres."
            )
        provenance = self._git_provider.resolve(repository_root, remote)
        if not provenance.branch:
            raise CalibrationHarnessError(
                "HEAD está detached; una campaña formal requiere rama explícita."
            )
        if provenance.head.lower() != expected_commit.lower():
            raise CalibrationHarnessError(
                f"HEAD {provenance.head} no coincide con {expected_commit}."
            )
        if provenance.dirty:
            raise CalibrationHarnessError(
                "El repositorio está dirty; la campaña formal falla de forma cerrada."
            )
        return provenance

    def _session_metadata(
        self,
        *,
        session_id: str,
        config: HarnessConfig,
        provenance: GitProvenance,
        expected_commit: str,
        started_at: datetime,
        status: str,
    ) -> dict[str, Any]:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "session_id": session_id,
            "purpose": "current_visual_price_stationary_burst_calibration",
            "experimental": True,
            "observation_only": True,
            "trading_or_platform_interaction": False,
            "ground_truth_classification_performed": False,
            "status": status,
            "started_at": started_at.isoformat(),
            "source_commit": provenance.head,
            "expected_commit": expected_commit,
            "git": _json_value(provenance),
            "configuration": _json_value(config),
            "capture_service_class": _class_identity(self._capture_service),
            "extractor_class": _class_identity(self._extractor),
            "resolver_class": _class_identity(
                getattr(self._extractor, "_search_window_resolver", None)
            ),
            "fixed_edge_override": getattr(
                self._extractor,
                "_effective_chart_right_x",
                None,
            ),
            "critical_section": {
                "capture_only": True,
                "extractor": False,
                "png": False,
                "filesystem": False,
                "strategy": False,
                "gui": False,
            },
        }

    @staticmethod
    def _analysis_payload(analysis: CurrentVisualPriceAnalysis) -> dict[str, Any]:
        extraction = analysis.extraction
        trace: CurrentVisualPriceDetectionTrace = analysis.trace
        price = extraction.price
        return {
            "status": extraction.status.value,
            "roi_y": price.roi_y if price is not None else None,
            "normalized_roi_y": (
                price.normalized_roi_y if price is not None else None
            ),
            "selected_x": extraction.selected_x,
            "selected_y": extraction.selected_y,
            "confidence": extraction.confidence,
            "candidate_count": extraction.candidate_count,
            "diagnostic": extraction.diagnostic,
            "source": price.source if price is not None else None,
            "roi_width": price.roi_width if price is not None else trace.image_width,
            "roi_height": (
                price.roi_height if price is not None else trace.image_height
            ),
            "effective_chart_right_x": trace.effective_chart_right_x,
            "effective_chart_right_source": trace.effective_chart_right_source,
            "semantic_diagnostic": (
                _json_value(trace.semantic_search)
                if trace.semantic_search is not None
                else None
            ),
            "trace": _json_value(trace),
        }

    @staticmethod
    def _geometry_payload(frame: Frame) -> dict[str, Any]:
        return {
            "chart_array_shape": [int(value) for value in frame.image.shape],
            "price_observation_array_shape": (
                [int(value) for value in frame.price_observation_image.shape]
                if frame.price_observation_image is not None
                else None
            ),
            "chart_region": _json_value(frame.chart_region),
            "price_observation_region": _json_value(
                frame.price_observation_region
            ),
        }

    @classmethod
    def _geometry_signature(cls, frame: Frame) -> str:
        payload = cls._geometry_payload(frame)
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _arrays_are_equal(first: np.ndarray, second: np.ndarray) -> bool:
        return (
            first.shape == second.shape
            and first.dtype == second.dtype
            and np.array_equal(first, second)
        )

    @staticmethod
    def _encode_png(image: np.ndarray) -> bytes:
        success, encoded = cv2.imencode(".png", image)
        if not success:
            raise ValueError("OpenCV no pudo codificar el PNG.")
        return encoded.tobytes()

    @staticmethod
    def _default_session_id() -> str:
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        return f"cvp_burst_{timestamp}_{uuid4().hex[:8]}"

    def _aware_wall_now(self) -> datetime:
        value = self._wall_clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise CalibrationHarnessError("wall_clock debe devolver datetime aware.")
        return value


def build_productive_capture_service() -> FrameCaptureService:
    """Construye la selección de ventana y captura productivas sin GUI."""

    return cast(
        FrameCaptureService,
        PocketOptionRuntimeFactory.create_capture_service(),
    )


def build_productive_extractor() -> PocketOptionCurrentVisualPriceExtractor:
    """Construye el extractor baseline sin fixed-edge ni thresholds alternativos."""

    return PocketOptionCurrentVisualPriceExtractor(
        search_window_resolver=(
            PocketOptionCurrentVisualPriceSearchWindowResolver()
        )
    )


def validate_external_output_directory(
    *,
    output_directory: Path,
    repository_root: Path,
) -> Path:
    """Rechaza cualquier output que resuelva dentro del repositorio."""

    repository = repository_root.resolve()
    output = output_directory.expanduser().resolve()
    if output == repository or output.is_relative_to(repository):
        raise CalibrationHarnessError(
            "output_dir debe estar fuera del repositorio y de .git."
        )
    if output.exists():
        if not output.is_dir():
            raise CalibrationHarnessError("output_dir existente no es un directorio.")
        if any(output.iterdir()):
            raise CalibrationHarnessError("output_dir debe estar vacío o no existir.")
    return output


def replay_current_visual_price_frame(
    *,
    session_directory: Path,
    frame_payload: Mapping[str, Any],
    extractor: VisualPriceTraceExtractor,
) -> CurrentVisualPriceAnalysis:
    """Reproduce determinísticamente el extractor desde el PNG publicado."""

    images = cast(Mapping[str, Any], frame_payload["images"])
    descriptor = cast(Mapping[str, Any], images["current_visual_price_input"])
    path = session_directory / cast(str, descriptor["filename"])
    encoded = path.read_bytes()
    if sha256(encoded).hexdigest() != descriptor["png_sha256"]:
        raise CalibrationHarnessError("El hash PNG no coincide con el manifest.")
    image = cv2.imdecode(
        np.frombuffer(encoded, dtype=np.uint8),
        cv2.IMREAD_UNCHANGED,
    )
    if image is None:
        raise CalibrationHarnessError("No se pudo decodificar el PNG de replay.")
    expected_shape = tuple(cast(Sequence[int], descriptor["shape"]))
    if image.shape != expected_shape or str(image.dtype) != descriptor["dtype"]:
        raise CalibrationHarnessError("Shape/dtype no coincide con el manifest.")
    if _pixel_sha256(image) != descriptor["pixel_sha256"]:
        raise CalibrationHarnessError("El pixel hash no coincide con el manifest.")
    return extractor.extract_with_trace(image)


def _pixel_sha256(image: np.ndarray) -> str:
    contiguous = np.ascontiguousarray(image)
    descriptor = (
        f"{contiguous.dtype.str}|{contiguous.shape}|".encode("ascii")
        + contiguous.tobytes(order="C")
    )
    return sha256(descriptor).hexdigest()


def _percentile(values: Sequence[int], fraction: float) -> float:
    if not values:
        raise ValueError("No se puede calcular percentil de una secuencia vacía.")
    index = (len(values) - 1) * fraction
    lower = int(index)
    upper = min(ceil(index), len(values) - 1)
    if lower == upper:
        return float(values[lower])
    return values[lower] + (values[upper] - values[lower]) * (index - lower)


def _class_identity(instance: object) -> str | None:
    if instance is None:
        return None
    cls = type(instance)
    return f"{cls.__module__}.{cls.__qualname__}"


def _json_value(value: object) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.generic):
        return value.item()
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _json_value(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_value(item) for item in value]
    raise TypeError(f"No se puede serializar {type(value).__name__} a JSON.")
