"""Bounded, opt-in persistence of mode-A originals, independent of h3/CVP."""

from __future__ import annotations

import ctypes
import hashlib
import json
import logging
import os
from collections import deque
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Condition, Lock, Thread
from time import perf_counter
from typing import Any, BinaryIO, cast
from uuid import uuid4

import cv2
import numpy as np

from pocket_option_analyzer.application.evidence.observational_evidence import (
    ObservationalEvidenceConfig,
    OriginalFrame,
)

logger = logging.getLogger(__name__)
ROLES = ("ENTRY", "PRE_EXPIRY", "SQ03_EXIT")


class _ConfinedFiles:
    """Private Windows file boundary, not a general filesystem abstraction.

    Trust Windows/local filesystem handle semantics, not directory contents.
    Pin every ancestor without write/delete sharing, open the leaf itself with
    OPEN_REPARSE_POINT, and inspect the handle BEFORE reading/writing. Reject
    ALL reparse tags, hard-linked files, aliases and replacement of the root.
    Rename/delete temporaries by their original handles, never by a stale name.
    This excludes a hostile kernel/admin, raw-volume access, same-process handle
    tampering and filesystem drivers that violate Windows sharing semantics.
    Unsupported platforms fail closed; no check-then-Path.open fallback.
    """

    def __init__(self, root: Path) -> None:
        if os.name != "nt":
            raise OSError("Confinement requires Windows handle semantics")
        from ctypes import wintypes

        self.ctypes = ctypes
        self.w = wintypes
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        self.api.CreateFileW.argtypes = (
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        )
        self.api.CreateFileW.restype = wintypes.HANDLE
        self.api.CloseHandle.argtypes = (wintypes.HANDLE,)
        self.api.CloseHandle.restype = wintypes.BOOL
        self.api.GetFileInformationByHandle.argtypes = (
            wintypes.HANDLE,
            wintypes.LPVOID,
        )
        self.api.GetFileInformationByHandle.restype = wintypes.BOOL
        self.api.GetFinalPathNameByHandleW.argtypes = (
            wintypes.HANDLE,
            wintypes.LPWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
        )
        self.api.GetFinalPathNameByHandleW.restype = wintypes.DWORD
        self.api.SetFileInformationByHandle.argtypes = (
            wintypes.HANDLE,
            ctypes.c_int,
            wintypes.LPVOID,
            wintypes.DWORD,
        )
        self.api.SetFileInformationByHandle.restype = wintypes.BOOL

        class Information(ctypes.Structure):
            _fields_ = [
                ("attributes", wintypes.DWORD),
                ("creation", wintypes.FILETIME),
                ("access", wintypes.FILETIME),
                ("write", wintypes.FILETIME),
                ("volume", wintypes.DWORD),
                ("size_high", wintypes.DWORD),
                ("size_low", wintypes.DWORD),
                ("links", wintypes.DWORD),
                ("index_high", wintypes.DWORD),
                ("index_low", wintypes.DWORD),
            ]

        self.information = Information
        self.root = root
        self.root_identity: tuple[int, int, int] | None = None
        self.blocked = False
        # Local drive paths only. No device namespace, UNC or alternate streams.
        if len(root.anchor) != 3 or root.anchor[1:] != ":\\":
            raise OSError("Confinement requires a local absolute drive path")
        with self.parents(root / ".boundary", create=True):
            pass

    def _open_handle(
        self, path: Path, access: int, disposition: int, *, directory: bool = False
    ) -> int:
        flags = 0x00200000 | (0x02000000 if directory else 0)  # no-follow/backup
        # Readers may coexist with our append; writers never share write/delete.
        share = 3 if access == 0x80000000 and not directory else 1
        handle = self.api.CreateFileW(
            str(path), access, share, None, disposition, flags, None
        )
        if handle == self.ctypes.c_void_p(-1).value:
            raise self.ctypes.WinError(self.ctypes.get_last_error())
        return int(handle)

    def _check(self, handle: int, path: Path, *, directory: bool) -> Any:
        info = self.information()
        if not self.api.GetFileInformationByHandle(handle, self.ctypes.byref(info)):
            raise self.ctypes.WinError(self.ctypes.get_last_error())
        if info.attributes & 0x400 or bool(info.attributes & 0x10) != directory:
            self.deny(f"reparse/type: {path}")
        if not directory and info.links != 1:
            self.deny(f"hard links: {path}")
        # Exact component identity, not a textual startswith confinement check.
        if os.path.normcase(self._final_name(handle)) != os.path.normcase(
            "\\\\?\\" + str(path)
        ):
            self.deny(f"physical alias: {path}")
        if path == self.root:
            identity = (info.volume, info.index_high, info.index_low)
            if self.root_identity is not None and self.root_identity != identity:
                self.deny("replaced root")
            self.root_identity = identity
        return info

    def _final_name(self, handle: int) -> str:
        buffer = self.ctypes.create_unicode_buffer(32768)
        length = self.api.GetFinalPathNameByHandleW(handle, buffer, len(buffer), 0)
        if not length or length >= len(buffer):
            self.deny("unverifiable handle")
        return str(buffer.value)

    def deny(self, reason: str) -> None:
        # A detected redirect poisons this writer, including later queued roles.
        # Reporting uses only the existing logger/counters, not an unsafe journal.
        self.blocked = True
        raise OSError(f"UNSAFE_EVIDENCE_PATH: {reason}")

    @contextmanager
    def parents(self, path: Path, *, create: bool = False) -> Iterator[int]:
        if self.blocked:
            raise OSError("UNSAFE_EVIDENCE_PATH: writer blocked")
        if not path.is_relative_to(self.root) or ".." in path.parts:
            raise OSError("UNSAFE_EVIDENCE_PATH: outside root")
        if any(part.rstrip(" .") != part or ":" in part for part in path.parts[1:]):
            raise OSError("UNSAFE_EVIDENCE_PATH: ambiguous component")
        with ExitStack() as stack:
            current = Path(path.anchor)
            # Attribute-only opens do NOT participate in Windows sharing checks.
            # GENERIC_READ includes directory data/list access, so deny-delete and
            # deny-write actually pin this component until its handle is closed.
            handle = self._open_handle(current, 0x80000000, 3, directory=True)
            stack.callback(self.api.CloseHandle, handle)
            self._check(handle, current, directory=True)
            for part in path.parent.parts[1:]:
                current /= part
                try:
                    handle = self._open_handle(current, 0x80000000, 3, directory=True)
                except FileNotFoundError:
                    if not create:
                        raise
                    try:
                        current.mkdir()
                    except FileExistsError:
                        pass  # A competing creation is checked via its handle.
                    handle = self._open_handle(current, 0x80000000, 3, directory=True)
                stack.callback(self.api.CloseHandle, handle)
                self._check(handle, current, directory=True)
            yield handle

    @contextmanager
    def open(
        self, path: Path, mode: str, *, delete: bool = False
    ) -> Iterator[BinaryIO]:
        import msvcrt

        access, disposition = {
            "rb": (0x80000000, 3),
            "ab": (0x40000000, 4),
            "xb": (0x40000000, 1),
        }[mode]
        with self.parents(path, create=mode != "rb"):
            handle = self._open_handle(
                path, access | (0x10000 if delete else 0), disposition
            )
            try:
                self._check(handle, path, directory=False)
                flags = os.O_BINARY | (os.O_RDONLY if mode == "rb" else os.O_WRONLY)
                if mode == "ab":
                    flags |= os.O_APPEND
                fd = msvcrt.open_osfhandle(handle, flags)
            except BaseException:
                self.api.CloseHandle(handle)
                raise
            with os.fdopen(fd, mode) as stream:
                yield cast(BinaryIO, stream)

    def read(self, path: Path) -> bytes:
        with self.open(path, "rb") as stream:
            return stream.read()

    def size(self, path: Path) -> int:
        with self.open(path, "rb") as stream:
            return os.fstat(stream.fileno()).st_size

    def exists(self, path: Path) -> bool:
        try:
            self.size(path)
        except FileNotFoundError:
            return False
        return True

    def files(self, directory: Path) -> Iterator[Path]:
        # Scan without following reparse points, including during recovery.
        with self.parents(directory / ".scan"):
            for child in directory.iterdir():
                attributes = child.lstat().st_file_attributes
                if attributes & 0x400:
                    self.deny(f"reparse: {child}")
                if attributes & 0x10:
                    yield from self.files(child)
                else:
                    self.size(child)  # Verify the opened leaf, not just lstat.
                    yield child

    def rename(self, stream: BinaryIO, target: Path) -> None:
        import msvcrt

        name = target.name

        class Rename(ctypes.Structure):
            _fields_ = [
                ("replace", self.w.DWORD),
                ("root", self.w.HANDLE),
                ("length", self.w.DWORD),
                ("name", self.w.WCHAR * (len(name) + 1)),
            ]

        with self.parents(target):
            self.exists(target)  # Reject redirected/hard-linked old manifests.
            handle = msvcrt.get_osfhandle(stream.fileno())
            source = Path(self._final_name(handle).removeprefix("\\\\?\\"))
            if source.parent != target.parent or target.name != "manifest.json":
                self.deny("manifest rename must stay in the opened source directory")
            info = Rename(1, None, len(name.encode("utf-16-le")), name)
            # Native simple-name + NULL root renames inside the source handle's
            # own directory, not CWD. No reopening of source/parent by pathname.
            native = self.ctypes.WinDLL("ntdll")
            native.NtSetInformationFile.argtypes = (
                self.w.HANDLE,
                self.w.LPVOID,
                self.w.LPVOID,
                self.w.ULONG,
                self.w.ULONG,
            )
            native.NtSetInformationFile.restype = self.w.LONG
            status_block = (self.ctypes.c_size_t * 2)()
            status = native.NtSetInformationFile(
                handle,
                status_block,
                self.ctypes.byref(info),
                self.ctypes.sizeof(info),
                10,
            )
            if status < 0:
                native.RtlNtStatusToDosError.argtypes = (self.w.LONG,)
                native.RtlNtStatusToDosError.restype = self.w.ULONG
                raise self.ctypes.WinError(native.RtlNtStatusToDosError(status))

    def discard(self, stream: BinaryIO) -> None:
        import msvcrt

        delete = self.w.BOOL(True)
        if not self.api.SetFileInformationByHandle(
            msvcrt.get_osfhandle(stream.fileno()),
            4,
            self.ctypes.byref(delete),
            self.ctypes.sizeof(delete),
        ):
            raise self.ctypes.WinError(self.ctypes.get_last_error())


@dataclass(frozen=True, slots=True)
class _Task:
    acceptance: dict[str, Any]
    roles: dict[str, OriginalFrame | None]
    closed: bool
    reason: str | None
    size: int


class ObservationalEvidenceWriter:
    """PNG work is off the producer thread; small census events are synchronous.

    Queue limits include active work. No global transaction/fsync guarantee.
    When even the bounded census journal cannot be written, scalar failure
    counters and the application logger report that census completeness is lost.
    No accepted originals are automatically deleted to make room.
    """

    def __init__(
        self, config: ObservationalEvidenceConfig, *, background: bool = True
    ) -> None:
        self.config = config
        # Do not resolve away a link before checking the configured boundary.
        self.directory = Path(os.path.abspath(config.directory))
        repository = next(
            parent
            for parent in Path(__file__).resolve().parents
            if (parent / "pyproject.toml").is_file()
        )
        if self.directory.is_relative_to(repository):
            raise ValueError("Experimental evidence must be outside the repository")
        self._files = _ConfinedFiles(self.directory)
        self._stored_bytes = sum(
            self._files.size(path) for path in self._files.files(self.directory)
        )
        self._condition = Condition()
        self._storage_lock = Lock()
        self._event_lock = Lock()
        self._tasks: deque[_Task] = deque()
        self._failed_tasks: deque[_Task] = deque()
        self._items = 0
        self._bytes = 0
        self._thread: Thread | None = None
        self._background = background
        self.failure_count = 0
        self.lost_event_count = 0
        self.last_error: str | None = None
        self.last_write_seconds: float | None = None
        self._recover_incomplete()

    @staticmethod
    def package_key(acceptance_id: str) -> str:
        return hashlib.sha256(acceptance_id.encode("utf-8")).hexdigest()

    def package_path(self, acceptance_id: str) -> Path:
        return (
            self.directory
            / "packages"
            / self.package_key(acceptance_id)
            / "manifest.json"
        )

    @property
    def queued_bytes(self) -> int:
        with self._condition:
            return self._bytes

    @property
    def queued_items(self) -> int:
        with self._condition:
            return self._items

    def _reserve(self, amount: int) -> None:
        with self._storage_lock:
            if self._stored_bytes + amount > self.config.max_storage_bytes:
                raise OSError("EXPERIMENTAL_STORAGE_LIMIT")
            # A failed/partial write keeps its reservation conservatively.
            self._stored_bytes += amount

    def _failure(self, error: Exception) -> None:
        self.failure_count += 1
        self.last_error = f"{type(error).__name__}: {error}"
        logger.warning("Observational originals incomplete: %s", self.last_error)

    def event(self, acceptance_id: str, event: str, **details: Any) -> bool:
        try:
            data = {
                "schema": "observational_evidence_event",
                "version": 1,
                "acceptance_id": acceptance_id,
                "event": event,
                "recorded_at": datetime.now(UTC).isoformat(),
                **details,
            }
            encoded = (
                json.dumps(data, ensure_ascii=False, allow_nan=False) + "\n"
            ).encode()
            with self._event_lock:
                self._reserve(len(encoded))
                with self._files.open(self.directory / "events.jsonl", "ab") as stream:
                    if stream.write(encoded) != len(encoded):
                        raise OSError("Incomplete experimental census write")
            return True
        except Exception as error:
            self.lost_event_count += 1
            self._failure(error)
            return False

    def submit(
        self,
        acceptance: dict[str, Any],
        roles: dict[str, OriginalFrame | None],
        *,
        closed: bool,
        reason: str | None = None,
    ) -> bool:
        size = len(json.dumps(acceptance).encode("utf-8")) + sum(
            frame.nbytes + len(frame.metadata_json.encode("utf-8"))
            for frame in roles.values()
            if frame is not None
        )
        # Detach mutable dictionaries before returning to the producer.
        task = _Task(
            json.loads(json.dumps(acceptance)), dict(roles), closed, reason, size
        )
        self.event(acceptance["acceptance_id"], "WRITE_PENDING", roles=list(roles))
        with self._condition:
            full = (
                self._items >= self.config.max_queue_items
                or self._bytes + size > self.config.max_queue_bytes
            )
            if not full:
                self._tasks.append(task)
                self._items += 1
                self._bytes += size
                if self._background and self._thread is None:
                    self._thread = Thread(target=self.drain, daemon=True)
                    self._thread.start()
        if full:
            self.event(
                acceptance["acceptance_id"], "EVIDENCE_LOST", reason="QUEUE_LIMIT"
            )
        return not full

    def drain(self) -> None:
        """Also usable synchronously by deterministic synthetic tests."""
        while True:
            with self._condition:
                if not self._tasks:
                    self._thread = None
                    self._condition.notify_all()
                    return
                task = self._tasks.popleft()
            started = perf_counter()
            succeeded = False
            try:
                succeeded = self._publish(task)
            except Exception as error:
                self._failure(error)
                self.event(
                    task.acceptance["acceptance_id"], "WRITE_FAILED", error=str(error)
                )
            finally:
                self.last_write_seconds = perf_counter() - started
                with self._condition:
                    if succeeded:
                        self._items -= 1
                        self._bytes -= task.size
                    else:
                        # Failed originals stay under the SAME queue budgets.
                        self._failed_tasks.append(task)
                    self._condition.notify_all()

    def retry_failed(self, acceptance_id: str) -> int:
        """Requeue owned originals, never a later capture or a new acceptance."""
        count = 0
        with self._condition:
            keep: deque[_Task] = deque()
            for task in self._failed_tasks:
                if task.acceptance["acceptance_id"] == acceptance_id:
                    self._tasks.append(task)
                    count += 1
                else:
                    keep.append(task)
            self._failed_tasks = keep
            if self._background and self._tasks and self._thread is None:
                self._thread = Thread(target=self.drain, daemon=True)
                self._thread.start()
        return count

    def discard_failed(self) -> None:
        """Explicit documented release, never silent eviction to admit new work."""
        with self._condition:
            failed = self._failed_tasks
            self._failed_tasks = deque()
            for task in failed:
                self._items -= 1
                self._bytes -= task.size
            self._condition.notify_all()
        for task in failed:
            self.event(
                task.acceptance["acceptance_id"],
                "EVIDENCE_LOST",
                reason="RETAINED_RETRY_EXPLICITLY_DISCARDED",
            )

    def flush(self, timeout: float) -> bool:
        with self._condition:
            return self._condition.wait_for(lambda: self._items == 0, timeout=timeout)

    def _atomic_manifest(self, path: Path, payload: dict[str, Any]) -> None:
        payload = {
            key: value for key, value in payload.items() if key != "manifest_sha256"
        }
        canonical = self._canonical(payload)
        payload["manifest_sha256"] = hashlib.sha256(canonical).hexdigest()
        encoded = self._canonical(payload)
        old_size = self._files.size(path) if self._files.exists(path) else 0
        # Both the old file and temporary new bytes coexist before replace.
        self._reserve(len(encoded))
        temporary = path.parent / f".{uuid4().hex}.tmp"
        with self._files.open(temporary, "xb", delete=True) as stream:
            try:
                if stream.write(encoded) != len(encoded):
                    raise OSError("Incomplete experimental manifest write")
                stream.flush()
                self._files.rename(stream, path)
                with self._storage_lock:
                    self._stored_bytes -= old_size
            except BaseException:
                self._files.discard(stream)
                raise

    def _image(self, image: np.ndarray) -> dict[str, Any]:
        success, encoded_array = cv2.imencode(".png", image)
        if not success:
            raise OSError("PNG_ENCODING_FAILED")
        decoded = cv2.imdecode(encoded_array, cv2.IMREAD_UNCHANGED)
        if decoded is None or not np.array_equal(decoded, image):
            raise OSError("PNG_PIXEL_MISMATCH")
        encoded = encoded_array.tobytes()
        digest = hashlib.sha256(encoded).hexdigest()
        relative = f"objects/{digest}.png"
        path = self.directory / relative
        if self._files.exists(path):
            if self._files.read(path) != encoded:
                raise OSError("EXISTING_ORIGINAL_CONFLICT")
        else:
            self._reserve(len(encoded))
            try:
                with self._files.open(path, "xb") as stream:
                    if stream.write(encoded) != len(encoded):
                        raise OSError("Incomplete experimental PNG write")
            except FileExistsError:
                if self._files.read(path) != encoded:
                    raise OSError("EXISTING_ORIGINAL_CONFLICT") from None
        return {
            "path": relative,
            "sha256": digest,
            "width": image.shape[1],
            "height": image.shape[0],
            "channels": image.shape[2] if image.ndim == 3 else 1,
            "dtype": str(image.dtype),
            "format": "PNG_LOSSLESS",
            "write_state": "WRITE_CONFIRMED",
        }

    def _publish(self, task: _Task) -> bool:
        identity = task.acceptance["acceptance_id"]
        path = self.package_path(identity)
        manifest = (
            self._read_manifest(path)
            if self._files.exists(path)
            else {
                "schema": "observational_originals",
                "version": 1,
                "acceptance_id": identity,
                "acceptance": task.acceptance,
                "instrument_identity": "UNKNOWN",
                "mode": "A",
                "nominal_outcome_verified": False,
                "closed": False,
                "roles": {},
                "failures": [],
            }
        )
        if manifest["acceptance"] != task.acceptance:
            raise ValueError("ACCEPTANCE_IDENTITY_CONFLICT")
        for role, frame in task.roles.items():
            if role not in ROLES:
                raise ValueError("Unknown original role")
            previous = manifest["roles"].get(role)
            if frame is None:
                if previous is None:
                    manifest["roles"][role] = {
                        "state": role + "_MISSING",
                        "reason": task.reason or "NO_FRAME",
                    }
                continue
            metadata = json.loads(frame.metadata_json)
            if previous and "frame" in previous:
                if previous["frame"] != metadata:
                    raise ValueError("SELECTED_FRAME_CONFLICT")
            images: dict[str, Any] = {}
            try:
                images = {name: self._image(image) for name, image in frame.images}
                if previous and previous.get("state") == "WRITE_CONFIRMED":
                    if previous["images"] != images:
                        raise ValueError("SELECTED_PIXELS_CONFLICT")
                manifest["roles"][role] = {
                    "state": "WRITE_CONFIRMED",
                    "availability": role + "_AVAILABLE",
                    "frame": metadata,
                    "images": images,
                    "logical_identity": [identity, role, metadata.get("frame_id")],
                }
            except Exception as error:
                if previous and previous.get("state") == "WRITE_CONFIRMED":
                    # Keep the original confirmed association on an incompatible retry.
                    raise
                manifest["roles"][role] = {
                    "state": "WRITE_FAILED",
                    "frame": metadata,
                    "images": images,
                }
                manifest["failures"].append(str(error))
                self._failure(error)
        manifest["closed"] = manifest["closed"] or task.closed
        if manifest["closed"]:
            for role in ROLES:
                manifest["roles"].setdefault(
                    role,
                    {"state": role + "_MISSING", "reason": task.reason or "NO_FRAME"},
                )
        complete = all(
            manifest["roles"].get(role, {}).get("state") == "WRITE_CONFIRMED"
            and self._role_integrity(manifest["roles"][role])
            for role in ROLES
        )
        manifest["package_state"] = (
            "PACKAGE_COMPLETE" if complete else "PACKAGE_PARTIAL"
        )
        manifest["write_state"] = (
            "WRITE_FAILED"
            if any(
                role.get("state") == "WRITE_FAILED"
                for role in manifest["roles"].values()
            )
            else "WRITE_CONFIRMED"
        )
        manifest["manifest_write_state"] = "WRITE_CONFIRMED"
        manifest["recorded_at"] = datetime.now(UTC).isoformat()
        self._atomic_manifest(path, manifest)
        self.event(
            identity,
            "MANIFEST_WRITE_CONFIRMED",
            package_state=manifest["package_state"],
        )
        return all(
            frame is None or manifest["roles"][role]["state"] == "WRITE_CONFIRMED"
            for role, frame in task.roles.items()
        )

    def _recover_incomplete(self) -> None:
        # Recovery marks old packages only; never resume their exit acquisition.
        journal = self.directory / "events.jsonl"
        if self._files.exists(journal):
            try:
                with self._files.open(journal, "rb") as stream:
                    for line in stream:
                        event = json.loads(line)
                        if event.get("event") == "ACCEPTANCE_KNOWN":
                            identity = event["acceptance_id"]
                            if not self._files.exists(self.package_path(identity)):
                                self.event(
                                    identity,
                                    "RESTART_UNPUBLISHED_ACCEPTANCE",
                                    evidence_lost=True,
                                )
            except Exception as error:
                self._failure(error)
        for path in self._files.files(self.directory):
            relative = path.relative_to(self.directory)
            if (
                len(relative.parts) != 3
                or relative.parts[0] != "packages"
                or relative.parts[2] != "manifest.json"
            ):
                continue
            try:
                manifest = self._read_manifest(path)
                damaged = False
                for role in manifest.get("roles", {}).values():
                    if role.get(
                        "state"
                    ) == "WRITE_CONFIRMED" and not self._role_integrity(role):
                        role["state"] = "WRITE_FAILED"
                        role["reason"] = "ORIGINAL_MISSING_OR_CORRUPT"
                        damaged = True
                if not manifest.get("closed", False) or damaged:
                    interrupted = not manifest.get("closed", False)
                    manifest["closed"] = True
                    manifest["package_state"] = "PACKAGE_PARTIAL"
                    manifest.setdefault("failures", []).append(
                        "RESTART_BEFORE_COMPLETION"
                        if interrupted
                        else "RECOVERY_INTEGRITY_FAILURE"
                    )
                    for role in ROLES:
                        manifest["roles"].setdefault(
                            role, {"state": role + "_MISSING", "reason": "RESTART"}
                        )
                    self._atomic_manifest(path, manifest)
            except Exception as error:
                self._failure(error)

    def _role_integrity(self, role: dict[str, Any]) -> bool:
        try:
            if "chart" not in role["images"]:
                return False
            for descriptor in role["images"].values():
                digest = descriptor["sha256"]
                if descriptor["path"] != f"objects/{digest}.png":
                    return False
                if len(digest) != 64 or any(
                    c not in "0123456789abcdef" for c in digest
                ):
                    return False
                path = self.directory / descriptor["path"]
                if hashlib.sha256(self._files.read(path)).hexdigest() != digest:
                    return False
            return True
        except (KeyError, OSError, TypeError, ValueError):
            return False

    @staticmethod
    def _canonical(payload: dict[str, Any]) -> bytes:
        return json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    def _read_manifest(self, path: Path) -> dict[str, Any]:
        payload: dict[str, Any] = json.loads(self._files.read(path).decode("utf-8"))
        digest = payload.pop("manifest_sha256", None)
        if hashlib.sha256(self._canonical(payload)).hexdigest() != digest:
            raise ValueError("MANIFEST_INTEGRITY_FAILURE")
        if (
            payload.get("schema") != "observational_originals"
            or payload.get("version") != 1
        ):
            raise ValueError("Unsupported experimental manifest")
        return payload

    def read_package(self, acceptance_id: str) -> dict[str, Any]:
        payload = self._read_manifest(self.package_path(acceptance_id))
        if payload["acceptance_id"] != acceptance_id:
            raise ValueError("ACCEPTANCE_IDENTITY_CONFLICT")
        for role in payload["roles"].values():
            if role.get("state") == "WRITE_CONFIRMED" and not self._role_integrity(
                role
            ):
                raise ValueError("ORIGINAL_INTEGRITY_FAILURE")
        return payload
