"""Read-only Git export, byte identity and committed-only product imports."""

from __future__ import annotations

import hashlib
import importlib.abc
import importlib.machinery
import importlib.metadata
import json
import os
import platform
import re
import stat
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

COMMIT = "0db4b65448746acf5cf1434df44d3f36576fcb42"
BRANCH = "feat/visual-price-resolution"
PROTECTED = dict(
    [
        (
            "src/pocket_option_analyzer/infrastructure/evidence/visual_evidence_serializer.py",
            "9d988afc9dbea15dabacbb21eafa6506f910059f9e5d8e469bad109df242f5bf",
        ),
        (
            "src/pocket_option_analyzer/vision/models/current_visual_price_detection_trace.py",
            "0deb9715291064788db79ca3d8a92f14a66f78790c9c651edcbd5e8d2d65cbb1",
        ),
        (
            "src/pocket_option_analyzer/vision/models/current_visual_price_search.py",
            "6d941b10f89ed92ce8909295d3a63d0b82dffcfebfb456918c2794d9752c847b",
        ),
        (
            "src/pocket_option_analyzer/vision/services/"
            "pocket_option_current_visual_price_extractor.py",
            "ee445e0e95b486a46a2bd22c085ceaaa5b44bb3e9f5585986ace0e71921de7da",
        ),
        (
            "src/pocket_option_analyzer/vision/services/"
            "pocket_option_current_visual_price_search_window_resolver.py",
            "f11073c8a2b4e71f04fdfd3b90723fe94d2dbb7c498918f340c26f2e7bf1d445",
        ),
    ]
)


class IsolationError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(repository: Path, *arguments: str) -> bytes:
    # No shell, no text transport of blob bytes, no index refresh.
    return subprocess.run(
        ["git", "--no-optional-locks", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
    ).stdout


def safe_relative(name: str) -> str:
    parts = name.split("/")
    if not parts or any(
        not part
        or part in (".", "..")
        or part.endswith((" ", "."))
        or re.search(r'[\\:<>"|?*\x00-\x1f]', part)
        or part.casefold() == ".git"
        or re.fullmatch(r"(?i)(con|prn|aux|nul|com[0-9]|lpt[0-9])(\..*)?", part)
        for part in parts
    ):
        raise IsolationError(f"Unsafe or ambiguous relative path: {name!r}")
    return name


def no_redirects(path: Path) -> Path:
    path = Path(os.path.abspath(path))
    if str(path).startswith("\\\\"):
        raise IsolationError("UNC/device paths are not admitted")
    for part in (*reversed(path.parents), path):
        if part.exists() or part.is_symlink():
            info = part.lstat()
            if part.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
                raise IsolationError(f"Redirected path: {part}")
            if part.is_file() and info.st_nlink != 1:
                raise IsolationError(f"Hard-linked file: {part}")
    return path


def outside(path: Path, *protected: Path) -> Path:
    path = no_redirects(path)
    for root in protected:
        root = no_redirects(root)
        if path.is_relative_to(root) or root.is_relative_to(path):
            raise IsolationError(f"Overlapping protected/output paths: {path}, {root}")
    return path


@dataclass(frozen=True)
class Blob:
    path: str
    oid: str
    sha256: str
    size: int
    mode: str


def tree_entries(repository: Path) -> list[tuple[str, str, str]]:
    entries = []
    seen: set[str] = set()
    for raw in git(repository, "ls-tree", "-rz", "--full-tree", COMMIT).split(b"\0"):
        if not raw:
            continue
        metadata, encoded_name = raw.split(b"\t", 1)
        mode, kind, oid = metadata.decode("ascii").split()
        name = safe_relative(encoded_name.decode("utf-8", errors="strict"))
        if kind != "blob" or mode not in {"100644", "100755"}:
            raise IsolationError(f"Unsupported Git entry: {name} {mode} {kind}")
        folded = name.casefold()
        if folded in seen:
            raise IsolationError(f"Case-colliding entry: {name}")
        seen.add(folded)
        entries.append((name, mode, oid))
    for name in seen:
        if any(
            "/".join(name.split("/")[:i]) in seen
            for i in range(1, len(name.split("/")))
        ):
            raise IsolationError("File/directory collision")
    return entries


def prepare_snapshot(repository: Path, destination: Path) -> dict[str, Any]:
    repository = no_redirects(repository)
    destination = outside(destination, repository)
    if destination.exists():
        raise IsolationError("Snapshot destination must be new")
    if git(repository, "rev-parse", f"{COMMIT}^{{commit}}").decode().strip() != COMMIT:
        raise IsolationError("Commit identity mismatch")
    entries = tree_entries(repository)  # Validate all paths BEFORE writing.
    if "pyproject.toml" not in {entry[0] for entry in entries}:
        raise IsolationError("Missing committed pyproject.toml")
    destination.mkdir(parents=True, exist_ok=False)
    blobs: list[Blob] = []
    with subprocess.Popen(
        ["git", "--no-optional-locks", "-C", str(repository), "cat-file", "--batch"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    ) as process:
        assert process.stdin is not None and process.stdout is not None
        for name, mode, oid in entries:
            process.stdin.write(oid.encode("ascii") + b"\n")
            process.stdin.flush()
            header = process.stdout.readline().decode("ascii").split()
            if len(header) != 3 or header[:2] != [oid, "blob"]:
                raise IsolationError("Unexpected cat-file response")
            size = int(header[2])
            data = process.stdout.read(size)
            if len(data) != size or process.stdout.read(1) != b"\n":
                raise IsolationError("Truncated blob")
            actual_oid = hashlib.sha1(
                f"blob {size}\0".encode("ascii") + data, usedforsecurity=False
            ).hexdigest()
            if actual_oid != oid:
                raise IsolationError("Git blob identity mismatch")
            path = destination / name
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                stream.write(data)
            blobs.append(Blob(name, oid, hashlib.sha256(data).hexdigest(), size, mode))
        process.stdin.close()
        if process.wait(timeout=30) != 0:
            raise IsolationError("cat-file failed")
    manifest = {
        "commit": COMMIT,
        "tree": git(repository, "rev-parse", f"{COMMIT}^{{tree}}").decode().strip(),
        "blobs": [asdict(blob) for blob in blobs],
    }
    verify_snapshot(destination, manifest)
    return manifest


def inventory(root: Path) -> dict[str, str]:
    no_redirects(root)
    result = {}
    if root.exists():
        for directory, subdirs, files in os.walk(root, followlinks=False):
            for name in (*subdirs, *files):
                path = no_redirects(Path(directory) / name)
                if path.is_file():
                    if not stat.S_ISREG(path.stat().st_mode):
                        raise IsolationError("Non-regular file")
                    result[path.relative_to(root).as_posix()] = sha256(path)
    return result


def verify_snapshot(root: Path, manifest: dict[str, Any]) -> None:
    if manifest["commit"] != COMMIT:
        raise IsolationError("Wrong snapshot commit")
    expected = {item["path"]: item["sha256"] for item in manifest["blobs"]}
    if inventory(root) != expected:
        raise IsolationError("Snapshot altered, missing files or unexpected files")


def repository_state(repository: Path) -> dict[str, Any]:
    paths = git(repository, "ls-files", "-z").decode("utf-8").split("\0")
    return {
        "branch": git(repository, "branch", "--show-current").decode().strip(),
        "head": git(repository, "rev-parse", "HEAD").decode().strip(),
        "staging": git(repository, "diff", "--cached", "--raw").decode(),
        "tracked_status": git(repository, "status", "--porcelain=v1", "-uno").decode(),
        "hashes": {p: sha256(repository / p) for p in paths if p},
    }


def require_baseline(state: dict[str, Any]) -> None:
    if state["head"] != COMMIT or state["branch"] != BRANCH or state["staging"]:
        raise IsolationError("Protected Git baseline/staging mismatch")
    dirty = {line[3:] for line in state["tracked_status"].splitlines()}
    if dirty != set(PROTECTED):
        raise IsolationError("Unexpected tracked working-tree changes")
    if any(state["hashes"].get(p) != value for p, value in PROTECTED.items()):
        raise IsolationError("Protected h3 hash mismatch")


class ProductImportGuard(importlib.abc.MetaPathFinder):
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def find_spec(self, fullname: str, path: Any = None, target: Any = None) -> Any:
        if fullname == "pocket_option_analyzer" or fullname.startswith(
            "pocket_option_analyzer."
        ):
            spec = importlib.machinery.PathFinder.find_spec(fullname, path)
            if spec is None:
                raise IsolationError(f"Unresolvable product module: {fullname}")
            locations = list(spec.submodule_search_locations or [])
            candidates = ([spec.origin] if spec.origin else []) + locations
            if not candidates or any(
                not Path(location).resolve().is_relative_to(self.root / "src")
                for location in candidates
            ):
                raise IsolationError(f"Import escaped snapshot: {fullname}")
            return spec
        return None


def product_origins(root: Path) -> dict[str, str]:
    result = {}
    for name, module in tuple(sys.modules.items()):
        if name == "pocket_option_analyzer" or name.startswith(
            "pocket_option_analyzer."
        ):
            origin = getattr(module, "__file__", None)
            locations = list(getattr(module, "__path__", []))
            candidates = ([origin] if origin else []) + locations
            if not candidates or any(
                not Path(location).resolve().is_relative_to(root / "src")
                for location in candidates
            ):
                raise IsolationError(f"Loaded product escaped snapshot: {name}")
            result[name] = str(Path(origin or locations[0]).resolve())
            for location in getattr(module, "__path__", []):
                if not Path(location).resolve().is_relative_to(root / "src"):
                    raise IsolationError(
                        f"Package search path escaped snapshot: {name}"
                    )
    return result


def activate_snapshot(root: Path, manifest: dict[str, Any]) -> None:
    root = root.resolve()
    verify_snapshot(root, manifest)
    product_origins(root)  # Reject a contaminated process; never unload/reimport it.
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(root / "src"))
    sys.meta_path.insert(0, ProductImportGuard(root))


def require_active_snapshot(root: Path) -> None:
    if not any(
        isinstance(finder, ProductImportGuard) and finder.root == root.resolve()
        for finder in sys.meta_path
    ):
        raise IsolationError("activate_snapshot must precede product construction")
    product_origins(root.resolve())


def environment_record() -> dict[str, Any]:
    return {
        "python": sys.version,
        "executable": sys.executable,
        "platform": platform.platform(),
        "dependencies": sorted(
            {
                f"{d.metadata['Name']}=={d.version}"
                for d in importlib.metadata.distributions()
            }
        ),
    }


def write_json(path: Path, value: Any) -> None:
    no_redirects(path)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
