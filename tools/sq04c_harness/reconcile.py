"""Read-only reconciliation after producer stop and explicit writer flush."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime
from math import isfinite
from pathlib import Path
from typing import Any, Protocol

from .isolation import inventory, no_redirects

ROLES = ("ENTRY", "PRE_EXPIRY", "SQ03_EXIT")
MISSING_REASONS = frozenset(
    {
        "NO_FRAME",
        "FRAME_BYTE_LIMIT",
        "UNSUPPORTED_IMAGE",
        "FRAME_IDENTITY_MISMATCH",
        "RETENTION_LIMIT",
        "RETENTION_EXPIRED",
        "SESSION_STOPPED_OR_INTERRUPTED",
        "RESTART",
    }
)
IDENTITY = (
    "execution_id",
    "evaluation_id",
    "frame_id",
    "observed_at",
    "source",
    "source_key",
    "session_key",
)


class PackageReader(Protocol):
    directory: Path

    def read_package(self, acceptance_id: str) -> dict[str, Any]: ...


@dataclass
class Census:
    """Independent observation of public native acceptance/evaluation objects."""

    acceptances: dict[str, dict[str, Any]] = field(default_factory=dict)
    evaluations: dict[str, dict[str, Any]] = field(default_factory=dict)
    observed_frames: list[dict[str, Any]] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)

    def evaluation(self, value: dict[str, Any]) -> None:
        identity = value["evaluation_id"]
        prior = self.evaluations.get(identity)
        if prior is not None and prior != value:
            self.conflicts.append(f"Evaluation identity conflict: {identity}")
        self.evaluations[identity] = json.loads(json.dumps(value))

    def acceptance(self, value: dict[str, Any]) -> None:
        identity = value["acceptance_id"]
        prior = self.acceptances.get(identity)
        if prior is not None and prior != value:
            self.conflicts.append(f"Acceptance identity conflict: {identity}")
        self.acceptances[identity] = json.loads(json.dumps(value))
        self.evaluation(value["evaluation"])


@dataclass
class Reconciliation:
    verified: bool
    packages: dict[str, str]
    issues: list[str]
    evidence_lost: list[str]
    files: dict[str, str]
    evidence_bytes: int
    coverage: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def json_lines(path: Path) -> list[dict[str, Any]]:
    no_redirects(path)
    if not path.exists():
        return []
    rows = [json.loads(line) for line in path.read_text("utf-8").splitlines()]
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError("Non-object journal row")
    return rows


def sq03_records(directory: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    # Include rotations, never select just the current file and hide lost census.
    accepted: dict[str, Any] = {}
    exits: dict[str, Any] = {}
    for relative in inventory(directory):
        name = Path(relative).name
        if not (
            name.startswith("signals.jsonl") or name.startswith("observations.jsonl")
        ):
            raise ValueError(f"Unexpected SQ03 file: {relative}")
        for row in json_lines(directory / relative):
            if "accepted_evidence" in row:
                payload = dict(row["accepted_evidence"])
                payload.pop("write_started_at", None)
                identity = payload["acceptance_id"]
                if identity in accepted:
                    raise ValueError(f"Duplicate SQ03 acceptance: {identity}")
                accepted[identity] = payload
            if row.get("event_type") == "accepted_signal_exit_evidence":
                if type(row.get("version")) is not int or row["version"] != 1:
                    raise ValueError("SQ03_EXIT_BINDING: unsupported exit version")
                payload = dict(row)
                payload.pop("write_started_at", None)
                identity = payload["acceptance_id"]
                if identity in exits:
                    raise ValueError(f"Duplicate SQ03 exit: {identity}")
                exits[identity] = payload
    return accepted, exits


def check_exit_binding(
    identity: str,
    acceptance: dict[str, Any],
    exit_record: dict[str, Any] | None,
    selected: list[dict[str, Any]],
    census: Census,
) -> None:
    """Verify native SQ03 v1 bindings, never a market settlement or outcome."""
    prefix = "SQ03_EXIT_BINDING: "
    if exit_record is None:
        if selected:
            raise ValueError(prefix + "selection journal has no SQ03 exit")
        return
    required = {
        "event_type",
        "version",
        "event_id",
        "acceptance_id",
        "entry_evaluation_id",
        "nominal_resolve_at",
        "observed_at",
        "lateness_seconds",
        "source_identity_available",
        "exit_evaluation",
    }
    if not required.issubset(exit_record) or len(selected) != 1:
        raise ValueError(prefix + "missing native exit fields or unique selection")
    journal = selected[0]
    if not {"exit_event_id", "exit_evaluation_id", "lateness_seconds"}.issubset(
        journal
    ):
        raise ValueError(prefix + "missing selection journal fields")
    entry = acceptance["evaluation"]
    evaluation = exit_record["exit_evaluation"]
    if not isinstance(evaluation, dict) or not set(IDENTITY).issubset(evaluation):
        raise ValueError(prefix + "missing exit evaluation identity")
    if (
        type(exit_record["version"]) is not int
        or exit_record["version"] != 1
        or exit_record["event_type"] != "accepted_signal_exit_evidence"
        or exit_record["acceptance_id"] != identity
        or acceptance["acceptance_id"] != identity
        or identity != entry["evaluation_id"] + ":accepted"
        or exit_record["entry_evaluation_id"] != entry["evaluation_id"]
        or exit_record["event_id"] != identity + ":exit"
        or journal["exit_event_id"] != exit_record["event_id"]
        or journal["exit_evaluation_id"] != evaluation["evaluation_id"]
        or any(
            evaluation[k] != entry[k]
            for k in ("execution_id", "source", "source_key", "session_key")
        )
    ):
        raise ValueError(prefix + "native entry/exit/journal identity mismatch")
    native = census.evaluations.get(evaluation["evaluation_id"])
    if native is None:
        raise ValueError(prefix + "EVALUATION_IDENTITY_UNVERIFIED: native exit")
    if any(k not in native or evaluation[k] != native[k] for k in IDENTITY):
        raise ValueError(
            prefix + "exit disagrees with independently observed evaluation"
        )
    if (
        exit_record["nominal_resolve_at"] != acceptance["nominal_resolve_at"]
        or exit_record["observed_at"] != evaluation["observed_at"]
    ):
        raise ValueError(prefix + "native time binding mismatch")
    try:
        nominal = datetime.fromisoformat(acceptance["nominal_resolve_at"])
        observed = datetime.fromisoformat(evaluation["observed_at"])
        if nominal.utcoffset() is None or observed.utcoffset() is None:
            raise ValueError("ambiguous timezone")
        lateness = (observed - nominal).total_seconds()
    except (ValueError, TypeError) as error:
        raise ValueError(prefix + "invalid native time binding") from error
    if lateness < 0 or any(
        type(value) not in (int, float) or not isfinite(value) or value != lateness
        for value in (exit_record["lateness_seconds"], journal["lateness_seconds"])
    ):
        raise ValueError(prefix + "native exit lateness mismatch")
    source_available = (
        evaluation["source_key"] is not None and evaluation["session_key"] is not None
    )
    if exit_record["source_identity_available"] is not source_available:
        raise ValueError(prefix + "source identity availability mismatch")


def check_roles(
    identity: str,
    package: dict[str, Any],
    acceptance: dict[str, Any],
    census: Census,
    exit_record: dict[str, Any] | None,
) -> tuple[str, set[str]]:
    if package["acceptance"] != acceptance or package["acceptance_id"] != identity:
        raise ValueError("Acceptance identity mismatch")
    if (
        package.get("closed") is not True
        or package.get("write_state") != "WRITE_CONFIRMED"
        or package.get("manifest_write_state") != "WRITE_CONFIRMED"
        or package.get("mode") != "A"
        or package.get("nominal_outcome_verified") is not False
    ):
        raise ValueError("Unclosed, failed or incompatible observational package")
    if set(package["roles"]) != set(ROLES):
        raise ValueError("Missing/unexpected role")
    referenced: set[str] = set()
    missing = []
    entry = acceptance["evaluation"]
    nominal = datetime.fromisoformat(acceptance["nominal_resolve_at"])
    for name in ROLES:
        role = package["roles"][name]
        if role["state"] != "WRITE_CONFIRMED":
            if (
                role["state"] != name + "_MISSING"
                or role.get("reason") not in MISSING_REASONS
            ):
                raise ValueError(f"Unjustified/failed role: {name}")
            if "frame" in role or "images" in role:
                raise ValueError("Missing role contains fabricated frame/images")
            missing.append(name)
            continue
        frame = role["frame"]
        evaluation = census.evaluations.get(frame["evaluation_id"])
        if evaluation is None:
            # Frame/time/geometry/PNG agreement cannot authenticate a native ID.
            # ObservedAnalysis has no public source for every intermediate ID.
            raise ValueError(f"EVALUATION_IDENTITY_UNVERIFIED: {name}")
        if any(
            k not in frame or k not in evaluation or frame[k] != evaluation[k]
            for k in IDENTITY
        ):
            raise ValueError(f"Different evaluation for {name}")
        if role["logical_identity"] != [identity, name, frame["frame_id"]]:
            raise ValueError("Role logical identity mismatch")
        if any(
            frame.get(k) != entry.get(k)
            for k in ("execution_id", "source", "source_key", "session_key")
        ):
            raise ValueError("Cross-session/source role")
        observed = datetime.fromisoformat(frame["observed_at"])
        if name == "ENTRY" and any(frame.get(k) != entry.get(k) for k in IDENTITY):
            raise ValueError("ENTRY is not the accepted evaluation")
        if name == "PRE_EXPIRY" and not (
            datetime.fromisoformat(entry["observed_at"]) <= observed < nominal
        ):
            raise ValueError("PRE_EXPIRY outside its observational interval")
        if name == "PRE_EXPIRY":
            observations = [*census.evaluations.values(), *census.observed_frames]
            candidates = [
                candidate
                for candidate in observations
                if all(
                    candidate.get(k) == entry.get(k)
                    for k in ("source", "source_key", "session_key")
                )
                and datetime.fromisoformat(entry["observed_at"])
                <= datetime.fromisoformat(candidate["observed_at"])
                < nominal
            ]
            if candidates and observed < max(
                datetime.fromisoformat(candidate["observed_at"])
                for candidate in candidates
            ):
                raise ValueError("PRE_EXPIRY substituted an older observation")
        if name == "SQ03_EXIT":
            if exit_record is None or any(
                frame.get(k) != exit_record["exit_evaluation"].get(k) for k in IDENTITY
            ):
                raise ValueError("SQ03_EXIT is not the native SQ03 selection")
        if "chart" not in role["images"]:
            raise ValueError("No original chart")
        for image in role["images"].values():
            digest = image["sha256"]
            if image["path"] != f"objects/{digest}.png":
                raise ValueError("Invalid object reference")
            referenced.add(image["path"])
    state = "PACKAGE_PARTIAL" if missing else "PACKAGE_COMPLETE"
    if package["package_state"] != state:
        raise ValueError("Package completeness contradicts roles")
    return state, referenced


def reconcile(
    writer: PackageReader, census: Census, sq03_directory: Path
) -> Reconciliation:
    issues = list(census.conflicts)
    packages: dict[str, str] = {}
    losses: list[str] = []
    files: dict[str, str] = {}
    evidence_bytes = 0
    try:
        files = inventory(writer.directory)
        evidence_bytes = sum((writer.directory / p).stat().st_size for p in files)
        events = json_lines(writer.directory / "events.jsonl")
        for event in events:
            if (
                event.get("schema") != "observational_evidence_event"
                or event.get("version") != 1
                or event.get("acceptance_id") not in census.acceptances
            ):
                raise ValueError("Unrecognized journal record/acceptance")
        known = Counter(
            e["acceptance_id"] for e in events if e.get("event") == "ACCEPTANCE_KNOWN"
        )
        if known != Counter(dict.fromkeys(census.acceptances, 1)):
            issues.append("ACCEPTANCE_KNOWN census mismatch")
        accepted, exits = sq03_records(sq03_directory)
        if accepted != census.acceptances:
            issues.append("SQ03/independent acceptance census mismatch")
        if not set(exits).issubset(accepted):
            issues.append("SQ03 exit without acceptance")
        losses = [
            e["acceptance_id"]
            for e in events
            if e.get("event") in {"EVIDENCE_LOST", "RESTART_UNPUBLISHED_ACCEPTANCE"}
            or e.get("evidence_lost")
        ]
        expected = {"events.jsonl"} if events else set()
        for identity, acceptance in census.acceptances.items():
            key = hashlib.sha256(identity.encode("utf-8")).hexdigest()
            path = f"packages/{key}/manifest.json"
            expected.add(path)
            try:
                identity_events = [e for e in events if e["acceptance_id"] == identity]
                selected = [
                    e for e in identity_events if e.get("event") == "SQ03_EXIT_SELECTED"
                ]
                check_exit_binding(
                    identity, acceptance, exits.get(identity), selected, census
                )
                package = writer.read_package(identity)  # Native hash + PNG checks.
                state, referenced = check_roles(
                    identity,
                    package,
                    acceptance,
                    census,
                    exits.get(identity),
                )
                packages[identity] = state
                expected.update(referenced)
                known_event = [
                    e for e in identity_events if e["event"] == "ACCEPTANCE_KNOWN"
                ]
                if (
                    len(known_event) != 1
                    or known_event[0].get("evaluation_id")
                    != acceptance["evaluation"]["evaluation_id"]
                ):
                    raise ValueError("Journal acceptance/evaluation identity mismatch")
                confirmed = [
                    e
                    for e in identity_events
                    if e["event"] == "MANIFEST_WRITE_CONFIRMED"
                ]
                if not confirmed or confirmed[-1].get("package_state") != state:
                    # Recovery changes an interrupted manifest without emitting a
                    # new confirmation; its frozen recovery marker explains that.
                    if "RESTART_BEFORE_COMPLETION" not in package.get("failures", []):
                        raise ValueError("No matching final manifest confirmation")
            except (OSError, ValueError, KeyError, TypeError) as error:
                packages[identity] = "PACKAGE_FAILED"
                issues.append(f"{identity}: {type(error).__name__}: {error}")
        if set(files) != expected:
            issues.append(f"Unreconciled files: {sorted(set(files) ^ expected)}")
    except (OSError, ValueError, KeyError, TypeError) as error:
        issues.append(f"{type(error).__name__}: {error}")
    if losses:
        issues.append("EVIDENCE_LOST: originals/census not fully preserved")
    return Reconciliation(
        not issues,
        packages,
        issues,
        losses,
        files,
        evidence_bytes,
        (
            "ACCEPTANCES_OBSERVED"
            if census.acceptances
            else "NO_ACCEPTANCES_COVERAGE_INCOMPLETE"
        ),
    )
