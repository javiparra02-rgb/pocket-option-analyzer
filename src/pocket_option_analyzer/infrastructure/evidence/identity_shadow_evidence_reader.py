from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .identity_shadow_evidence_serializer import (
    IdentityShadowEvidenceSerializer,
)


class IdentityShadowEvidenceReader:
    """Pure ordered JSONL reader with schema and hash-chain validation."""

    def __init__(self, directory: Path) -> None:
        self._directory = Path(directory)

    def read_frames(self) -> tuple[dict[str, Any], ...]:
        records = self._read_stream(
            self._directory / "identity_shadow/frames.jsonl"
        )
        for payload in records:
            self._validate_decision_telemetry(payload)
        return records

    def read_events(self) -> tuple[dict[str, Any], ...]:
        return self._read_stream(self._directory / "identity_shadow/events.jsonl")

    @staticmethod
    def _read_stream(path: Path) -> tuple[dict[str, Any], ...]:
        if not path.exists():
            return ()
        records: list[dict[str, Any]] = []
        previous_hash: str | None = None
        with path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as error:
                    raise ValueError(
                        f"Invalid identity JSON at line {line_number}."
                    ) from error
                if not isinstance(payload, dict):
                    raise ValueError("Identity JSONL records must be objects.")
                if payload.get("identity_shadow_schema_version") != (
                    IdentityShadowEvidenceSerializer.SCHEMA_VERSION
                ):
                    raise ValueError("Unsupported identity shadow schema.")
                if payload.get("sequence_number") != len(records) + 1:
                    raise ValueError("Identity sequence is not contiguous.")
                if payload.get("previous_record_sha256") != previous_hash:
                    raise ValueError("Identity hash chain is inconsistent.")
                persisted_hash = payload.get("record_sha256")
                unhashed = dict(payload)
                unhashed.pop("record_sha256", None)
                expected_hash = IdentityShadowEvidenceSerializer.payload_sha256(
                    unhashed
                )
                if persisted_hash != expected_hash:
                    raise ValueError("Identity record hash does not match payload.")
                previous_hash = str(persisted_hash)
                records.append(payload)
        return tuple(records)

    @staticmethod
    def _validate_decision_telemetry(payload: dict[str, Any]) -> None:
        version = payload.get("identity_decision_telemetry_schema_version")
        if version is None:
            return
        if version != (
            IdentityShadowEvidenceSerializer.DECISION_TELEMETRY_SCHEMA_VERSION
        ):
            raise ValueError("Unsupported identity decision telemetry schema.")
        required = {
            "trusted_rollover_evaluation",
            "terminal_seed_evaluation",
            "bootstrap_confirmation_evaluation",
            "tracking_terminal_evaluation",
        }
        if not required.issubset(payload):
            raise ValueError("Identity decision telemetry is incomplete.")
        structures = tuple(payload[name] for name in required)
        if any(not isinstance(value, dict) for value in structures):
            raise ValueError("Identity decision telemetry must contain objects.")
        trusted = payload["trusted_rollover_evaluation"]
        if trusted.get("status") not in {"not_evaluated", "accepted", "rejected"}:
            raise ValueError("Invalid trusted rollover evaluation status.")
        terminal = payload["terminal_seed_evaluation"]
        if terminal.get("status") not in {
            "not_evaluated",
            "observed",
            "absent",
            "ambiguous",
            "overlay",
            "invalid_geometry",
        }:
            raise ValueError("Invalid terminal seed evaluation status.")
