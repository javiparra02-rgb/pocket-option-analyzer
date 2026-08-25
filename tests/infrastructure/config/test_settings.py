from pathlib import Path
from typing import get_type_hints

import pytest

from pocket_option_analyzer.infrastructure.config import Settings


def test_visual_evidence_directory_defaults_to_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("VISUAL_EVIDENCE_DIRECTORY", raising=False)

    settings = Settings(_env_file=None)

    assert settings.visual_evidence_directory is None


def test_visual_evidence_directory_reads_exact_environment_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "VISUAL_EVIDENCE_DIRECTORY",
        "logs/calibration/session/evidence",
    )

    settings = Settings(_env_file=None)

    assert settings.visual_evidence_directory == Path(
        "logs/calibration/session/evidence"
    )


def test_visual_evidence_relative_path_keeps_project_convention() -> None:
    settings = Settings(
        _env_file=None,
        visual_evidence_directory="logs/calibration/relative/evidence",
    )

    assert settings.visual_evidence_directory == Path(
        "logs/calibration/relative/evidence"
    )
    assert settings.visual_evidence_directory.is_absolute() is False


def test_settings_public_type_hints_resolve() -> None:
    assert get_type_hints(Settings)


def test_identity_evidence_defaults_to_fully_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "VISUAL_IDENTITY_EVIDENCE_ENABLED",
        "VISUAL_IDENTITY_EVIDENCE_RING_BUFFER_SIZE",
        "VISUAL_IDENTITY_EVIDENCE_PRE_EVENT_TRACE_COUNT",
        "VISUAL_IDENTITY_EVIDENCE_INTENSIVE_PNG",
        "VISUAL_IDENTITY_EVIDENCE_CHECKPOINT_INTERVAL_FRAMES",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = Settings(_env_file=None)

    assert settings.visual_identity_evidence_enabled is False
    assert settings.visual_identity_evidence_ring_buffer_size == 30
    assert settings.visual_identity_evidence_pre_event_trace_count == 5
    assert settings.visual_identity_evidence_intensive_png is False
    assert settings.visual_identity_evidence_checkpoint_interval_frames is None


def test_identity_evidence_reads_all_opt_in_environment_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VISUAL_IDENTITY_EVIDENCE_ENABLED", "true")
    monkeypatch.setenv("VISUAL_IDENTITY_EVIDENCE_RING_BUFFER_SIZE", "45")
    monkeypatch.setenv("VISUAL_IDENTITY_EVIDENCE_PRE_EVENT_TRACE_COUNT", "7")
    monkeypatch.setenv("VISUAL_IDENTITY_EVIDENCE_INTENSIVE_PNG", "true")
    monkeypatch.setenv(
        "VISUAL_IDENTITY_EVIDENCE_CHECKPOINT_INTERVAL_FRAMES",
        "60",
    )

    settings = Settings(_env_file=None)

    assert settings.visual_identity_evidence_enabled is True
    assert settings.visual_identity_evidence_ring_buffer_size == 45
    assert settings.visual_identity_evidence_pre_event_trace_count == 7
    assert settings.visual_identity_evidence_intensive_png is True
    assert settings.visual_identity_evidence_checkpoint_interval_frames == 60
