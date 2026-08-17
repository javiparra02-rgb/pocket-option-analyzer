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
