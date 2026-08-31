from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from scripts.capture_current_visual_price_bursts import build_parser, main

COMMIT = "8f5e68afa92d54686662e324b17136e30997a708"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_parser_defaults_are_explicit_and_candidate_only(tmp_path: Path) -> None:
    arguments = build_parser().parse_args(
        [
            "--output-dir",
            str(tmp_path / "evidence"),
            "--expected-commit",
            COMMIT,
        ]
    )

    assert arguments.frames_per_burst == 5
    assert arguments.target_fps == 8.0
    assert arguments.candidate_bursts == 20
    assert arguments.preflight_frames == 30
    assert arguments.inter_burst_delay == 0.0


@pytest.mark.parametrize("missing", ["output", "commit"])
def test_required_formal_arguments_fail_closed(missing: str, tmp_path: Path) -> None:
    arguments = []
    if missing != "output":
        arguments.extend(["--output-dir", str(tmp_path / "evidence")])
    if missing != "commit":
        arguments.extend(["--expected-commit", COMMIT])

    with pytest.raises(SystemExit) as error:
        build_parser().parse_args(arguments)

    assert error.value.code == 2


def test_main_validates_ranges_before_constructing_live_capture(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as error:
        main(
            [
                "--output-dir",
                str(tmp_path / "evidence"),
                "--expected-commit",
                COMMIT,
                "--frames-per-burst",
                "4",
            ]
        )

    assert error.value.code == 2


def test_help_is_functional_from_direct_script_invocation() -> None:
    completed = subprocess.run(
        (
            sys.executable,
            str(REPOSITORY_ROOT / "scripts/capture_current_visual_price_bursts.py"),
            "--help",
        ),
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    help_text = completed.stdout
    assert "EXPERIMENTAL" in help_text
    assert "no hace trading" in help_text
    assert "candidate burst NO es un burst S0" in help_text
    assert "fuera del repositorio" in help_text
    assert "--expected-commit" in help_text


def test_all_required_cli_switches_are_exposed() -> None:
    help_text = build_parser().format_help()

    for switch in (
        "--frames-per-burst",
        "--target-fps",
        "--candidate-bursts",
        "--output-dir",
        "--preflight-frames",
        "--expected-commit",
        "--inter-burst-delay",
    ):
        assert switch in help_text
