"""Tests must run in the committed-only child process, never the editable product."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from sq04c_harness.config import HarnessConfig
from sq04c_harness.isolation import require_active_snapshot

SNAPSHOT = Path(os.environ["SQ04C_SNAPSHOT"])
RUN = Path(os.environ["SQ04C_RUN"])
require_active_snapshot(SNAPSHOT)


@pytest.fixture
def config(tmp_path: Path) -> HarnessConfig:
    return HarnessConfig(
        mode="SYNTHETIC",
        capture_observational=True,
        pipeline_observational=True,
        budgets={
            "max_frame_bytes": 8 * 1024**2,
            "max_retained_bytes": 32 * 1024**2,
            "max_pending_acceptances": 4,
            "max_queue_items": 8,
            "max_queue_bytes": 64 * 1024**2,
            "max_storage_bytes": 256 * 1024**2,
            "pending_retention_seconds": 60,
            "context_region": None,
        },
        interval_seconds=0,
        join_timeout=5,
        flush_timeout=5,
        max_cycles=3,
        sample_capacity=16,
        snapshot=SNAPSHOT,
        repository=Path(__file__).resolve().parents[3],
        evidence=tmp_path / "originals",
        sq03=tmp_path / "sq03",
        supervision=tmp_path / "supervision",
    )


@pytest.fixture
def native_package(config: HarnessConfig) -> Any:
    from .fixtures import NativePackage

    return NativePackage(config)
