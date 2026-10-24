"""Run only the new harness tests against a binary committed snapshot.

Call with the venv interpreter and -I -B. No shell, GUI, live mode or network.
Outputs are retained; no automatic recursive cleanup is performed.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sq04c_harness.isolation import (  # noqa: E402
    activate_snapshot,
    environment_record,
    inventory,
    outside,
    prepare_snapshot,
    product_origins,
    repository_state,
    require_baseline,
    verify_snapshot,
    write_json,
)


def child(run: Path, test_filter: str | None = None) -> int:
    manifest = json.loads((run / "snapshot_identity.json").read_text("utf-8"))
    snapshot = run / "snapshot"
    activate_snapshot(snapshot, manifest)
    os.environ["SQ04C_SNAPSHOT"] = str(snapshot)
    os.environ["SQ04C_RUN"] = str(run)
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    os.environ.pop("PYTEST_ADDOPTS", None)
    os.environ.pop("PYTHONPATH", None)
    os.environ["TEMP"] = os.environ["TMP"] = str(run / "temporary")
    (run / "temporary").mkdir()
    os.chdir(run / "results")
    import pytest

    tests = Path(__file__).resolve().parent / "tests"
    status = pytest.main(
        [
            str(tests),
            "--confcutdir=" + str(tests),
            "--rootdir=" + str(tests),
            "-c",
            str(snapshot / "pyproject.toml"),
            "-o",
            "pythonpath=",
            "-p",
            "no:cacheprovider",
            "--basetemp=" + str(run / "pytest-tmp"),
            "--junitxml=" + str(run / "results" / "junit.xml"),
            "-ra",
            "-q",
        ]
        + (["-k", test_filter] if test_filter else [])
    )
    origins = product_origins(snapshot)
    verify_snapshot(snapshot, manifest)
    write_json(run / "results" / "import_provenance.json", origins)
    write_json(run / "results" / "environment.json", environment_record())
    return int(status)


def validate(
    repository: Path, output_parent: Path, test_filter: str | None = None
) -> tuple[int, Path]:
    output_parent = outside(output_parent, repository)
    before = repository_state(repository)
    require_baseline(before)
    output_parent.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="sq04c-s8-", dir=output_parent))
    (run / "results").mkdir()
    write_json(run / "repository_before.json", before)
    harness = Path(__file__).resolve().parent
    harness_before = inventory(harness)
    write_json(run / "harness_hashes.json", harness_before)
    result: dict[str, Any] = {"verdict": "SQ04C_S8_INCOMPLETE", "mode": "SYNTHETIC"}
    result["test_selection"] = test_filter or "FULL_HARNESS_SUITE"
    status = 1
    try:
        manifest = prepare_snapshot(repository, run / "snapshot")
        write_json(run / "snapshot_identity.json", manifest)
        command = [
            sys.executable,
            "-I",
            "-B",
            str(Path(__file__).resolve()),
            "--child",
            str(run),
        ]
        if test_filter:
            command.extend(["--test-filter", test_filter])
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        environment.pop("PYTEST_ADDOPTS", None)
        with (run / "results" / "pytest-transcript.txt").open("xb") as transcript:
            completed = subprocess.run(
                command,
                cwd=run,
                env=environment,
                stdout=transcript,
                stderr=subprocess.STDOUT,
                check=False,
            )
        status = completed.returncode
        verify_snapshot(run / "snapshot", manifest)
        if inventory(harness) != harness_before:
            raise RuntimeError("Harness source changed during validation")
        result["pytest_exit_code"] = status
        from xml.etree import ElementTree

        junit = ElementTree.parse(run / "results" / "junit.xml")
        cases = list(junit.iter("testcase"))
        counts = {
            "tests": len(cases),
            "failures": len(list(junit.iter("failure"))),
            "errors": len(list(junit.iter("error"))),
            "skipped": len(list(junit.iter("skipped"))),
        }
        result["counts"] = counts
        passed = (
            status == 0
            and counts["tests"] > 0
            and all(counts[key] == 0 for key in ("failures", "errors", "skipped"))
        )
        result["verdict"] = (
            "SQ04C_S8_SYNTHETIC_VALIDATION_PASSED"
            if passed
            else "SQ04C_S8_VALIDATION_FAILED"
        )
        status = 0 if passed else 1
    except Exception:
        status = 1
        result["error"] = traceback.format_exc()
        result["verdict"] = "SQ04C_S8_ISOLATION_FAILED"
    finally:
        after = repository_state(repository)
        write_json(run / "repository_after.json", after)
        result["original_repository_unchanged"] = before == after
        if before != after:
            result["verdict"] = "SQ04C_S8_PROTECTED_STATE_CHANGED"
            status = 1
        write_json(run / "results" / "validation.json", result)
    return status, run


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path)
    parser.add_argument("--output-parent", type=Path)
    parser.add_argument("--child", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--test-filter", help="Explicit pytest -k selection, recorded")
    args = parser.parse_args()
    if args.child is not None:
        return child(args.child, args.test_filter)
    if args.repository is None or args.output_parent is None:
        parser.error("--repository and --output-parent are required")
    status, run = validate(
        args.repository.resolve(), args.output_parent, args.test_filter
    )
    print(f"VALIDATION_DIRECTORY={run}")
    print((run / "results" / "validation.json").read_text("utf-8"))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
