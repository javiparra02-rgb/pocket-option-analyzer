"""Windows-only synthetic filesystem attacks; never capture or use user data."""

from __future__ import annotations

import hashlib
import json
import os
from types import SimpleNamespace

import numpy as np
import pytest
from test_observational_originals import config

from pocket_option_analyzer.application.evidence.observational_evidence import (
    OriginalFrame,
)
from pocket_option_analyzer.infrastructure.evidence.observational_evidence_writer import (  # noqa: E501
    ObservationalEvidenceWriter,
)

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows handle boundary")


def inventory(directory):
    return {
        str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in directory.rglob("*")
        if path.is_file()
    }


@pytest.fixture
def boundary(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel.bin"
    sentinel.write_bytes(b"synthetic exterior: MUST NOT CHANGE\x00\xff")
    before = inventory(outside)
    cfg = config(tmp_path)
    writer = ObservationalEvidenceWriter(cfg, background=False)
    yield writer, outside, sentinel
    assert inventory(outside) == before  # hashes AND absence of new files


def redirect(link, target, kind="symlink"):
    link.parent.mkdir(parents=True, exist_ok=True)
    if kind == "hardlink":
        os.link(target, link)
        assert link.stat().st_nlink > 1
    elif kind == "junction":
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
        assert link.is_junction()
    else:
        try:
            link.symlink_to(target, target_is_directory=target.is_dir())
        except OSError as error:
            if error.winerror == 1314:
                pytest.skip("Windows did not grant symlink creation privilege")
            raise
        assert link.is_symlink()


def publish(writer, *, pixels=17):
    frame = OriginalFrame(
        json.dumps({"frame_id": 1, "evaluation_id": "synthetic:1"}),
        (("chart", np.full((20, 20, 3), pixels, dtype=np.uint8)),),
    )
    assert writer.submit(
        {"acceptance_id": "synthetic:1:accepted"},
        dict.fromkeys(("ENTRY", "PRE_EXPIRY", "SQ03_EXIT"), frame),
        closed=True,
    )
    writer.drain()
    return "synthetic:1:accepted"


def assert_not_confirmed(writer):
    assert writer.failure_count > 0
    assert writer.queued_items == 1  # same failed task retained, no new acceptance
    path = writer.package_path("synthetic:1:accepted")
    if path.exists() and not path.is_symlink() and path.stat().st_nlink == 1:
        manifest = json.loads(path.read_bytes())
        assert manifest["package_state"] != "PACKAGE_COMPLETE"
        assert manifest["write_state"] != "WRITE_CONFIRMED"
    journal = writer.directory / "events.jsonl"
    if journal.exists() and not journal.is_symlink() and journal.stat().st_nlink == 1:
        events = [json.loads(line) for line in journal.read_bytes().splitlines()]
        assert not any(e["event"] == "MANIFEST_WRITE_CONFIRMED" for e in events)
        assert all(e["acceptance_id"] == "synthetic:1:accepted" for e in events)


def test_event_symlink_fails_closed_for_entire_package(boundary):
    writer, _, sentinel = boundary
    redirect(writer.directory / "events.jsonl", sentinel)
    assert not writer.event("synthetic:1:accepted", "ACCEPTANCE_KNOWN")
    publish(writer)
    assert_not_confirmed(writer)
    assert writer.lost_event_count > 0


@pytest.mark.parametrize("kind", ["symlink", "junction"])
@pytest.mark.parametrize("location", ["objects", "packages", "acceptance"])
def test_directory_redirects_never_receive_png_or_manifest(boundary, kind, location):
    writer, outside, _ = boundary
    path = writer.directory / location
    if location == "acceptance":
        path = writer.package_path("synthetic:1:accepted").parent
    redirect(path, outside, kind)
    publish(writer)
    assert_not_confirmed(writer)


@pytest.mark.parametrize("leaf", ["manifest", "png", "temporary"])
@pytest.mark.parametrize("kind", ["symlink", "hardlink"])
def test_redirected_leaf_is_never_overwritten(boundary, monkeypatch, leaf, kind):
    writer, _, sentinel = boundary
    if leaf == "manifest":
        path = writer.package_path("synthetic:1:accepted")
    elif leaf == "temporary":
        path = writer.package_path("synthetic:1:accepted").parent / ".fixed.tmp"
        monkeypatch.setattr(
            "pocket_option_analyzer.infrastructure.evidence."
            "observational_evidence_writer.uuid4",
            lambda: SimpleNamespace(hex="fixed"),
        )
    else:
        import cv2

        ok, encoded = cv2.imencode(".png", np.full((20, 20, 3), 17, dtype=np.uint8))
        assert ok
        digest = hashlib.sha256(encoded.tobytes()).hexdigest()
        path = writer.directory / "objects" / f"{digest}.png"
    redirect(path, sentinel, kind)
    publish(writer)
    assert_not_confirmed(writer)


def test_hard_link_event_is_rejected(boundary):
    writer, _, sentinel = boundary
    os.link(sentinel, writer.directory / "events.jsonl")
    assert not writer.event("synthetic:1:accepted", "ACCEPTANCE_KNOWN")
    publish(writer)
    assert_not_confirmed(writer)


@pytest.mark.parametrize("kind", ["symlink", "junction"])
@pytest.mark.parametrize("location", ["root", "ancestor"])
def test_redirected_root_or_ancestor_is_rejected_before_creation(
    tmp_path, kind, location
):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "sentinel").write_bytes(b"root sentinel")
    before = inventory(outside)
    cfg = config(tmp_path)
    path = cfg.directory if location == "root" else tmp_path / "parent"
    redirect(path, outside, kind)
    if location == "ancestor":
        from dataclasses import replace

        cfg = replace(cfg, directory=path / "originals")
    with pytest.raises(OSError, match="UNSAFE_EVIDENCE_PATH"):
        ObservationalEvidenceWriter(cfg, background=False)
    assert inventory(outside) == before


@pytest.mark.parametrize("location", ["events.jsonl", "objects", "packages"])
def test_restart_rejects_existing_redirections(boundary, location):
    writer, outside, sentinel = boundary
    redirect(
        writer.directory / location,
        sentinel if location == "events.jsonl" else outside,
        "symlink" if location == "events.jsonl" else "junction",
    )
    with pytest.raises(OSError, match="UNSAFE_EVIDENCE_PATH"):
        ObservationalEvidenceWriter(writer.config, background=False)


def test_safe_append_publish_and_identical_retry_preserve_hashes(boundary):
    writer, _, _ = boundary
    assert writer.event("synthetic:1:accepted", "ACCEPTANCE_KNOWN")
    identity = publish(writer)
    before = writer.read_package(identity)
    assert before["package_state"] == "PACKAGE_COMPLETE"
    assert writer.queued_items == 0
    publish(writer)
    after = writer.read_package(identity)
    assert before["roles"] == after["roles"]
    assert before["acceptance_id"] == after["acceptance_id"]
    assert writer.event(identity, "SECOND_APPEND")
    assert b"SECOND_APPEND" in (writer.directory / "events.jsonl").read_bytes()
    publish(writer, pixels=29)
    assert writer.failure_count > 0
    assert writer.read_package(identity)["roles"] == before["roles"]


def test_ancestor_swap_after_validation_is_denied_by_windows(boundary, monkeypatch):
    writer, outside, _ = boundary
    path = writer.directory / "objects"
    path.mkdir()
    checked = writer._files._check
    attempted = []

    def swap(handle, checked_path, *, directory):
        result = checked(handle, checked_path, directory=directory)
        if checked_path == path and not attempted:
            try:
                path.rename(path.with_name("displaced"))
            except PermissionError as error:
                attempted.append(error.winerror)
            else:
                redirect(path, outside, "junction")
                pytest.fail("Windows allowed replacement of a pinned ancestor")
        return result

    monkeypatch.setattr(writer._files, "_check", swap)
    identity = publish(writer)
    assert attempted == [32]  # ERROR_SHARING_VIOLATION, not a preflight check
    assert writer.read_package(identity)["package_state"] == "PACKAGE_COMPLETE"


def test_leaf_swap_between_open_and_write_is_denied(boundary, monkeypatch):
    writer, _, _ = boundary
    path = writer.directory / "events.jsonl"
    checked = writer._files._check
    attempted = []

    def swap(handle, checked_path, *, directory):
        result = checked(handle, checked_path, directory=directory)
        if checked_path == path and not attempted:
            with pytest.raises(PermissionError) as error:
                path.rename(path.with_suffix(".displaced"))
            attempted.append(error.value.winerror)
        return result

    monkeypatch.setattr(writer._files, "_check", swap)
    assert writer.event("synthetic:1:accepted", "PINNED_APPEND")
    assert attempted == [32]


@pytest.mark.parametrize("location", ["events.jsonl", "objects"])
def test_redirect_inserted_at_open_is_rejected(boundary, monkeypatch, location):
    writer, outside, sentinel = boundary
    path = writer.directory / location
    opening = writer._files._open_handle
    inserted = []

    def insert(open_path, access, disposition, *, directory=False):
        if open_path == path and not inserted:
            redirect(
                path,
                sentinel if location == "events.jsonl" else outside,
                "symlink" if location == "events.jsonl" else "junction",
            )
            inserted.append(True)
        return opening(open_path, access, disposition, directory=directory)

    monkeypatch.setattr(writer._files, "_open_handle", insert)
    publish(writer)
    assert inserted
    assert_not_confirmed(writer)


def test_root_replacement_between_operations_is_detected(boundary):
    writer, _, _ = boundary
    writer.directory.rename(writer.directory.with_name("old-originals"))
    writer.directory.mkdir()
    assert not writer.event("synthetic:1:accepted", "MUST_NOT_WRITE")
    assert not (writer.directory / "events.jsonl").exists()


def test_temporary_is_pinned_through_handle_rename(boundary, monkeypatch):
    writer, _, _ = boundary
    rename = writer._files.rename
    attempts = []

    def attempt(stream, target):
        paths = list(target.parent.glob("*.tmp"))
        assert len(paths) == 1
        with pytest.raises(PermissionError) as error:
            paths[0].rename(paths[0].with_suffix(".displaced"))
        attempts.append(error.value.winerror)
        return rename(stream, target)

    monkeypatch.setattr(writer._files, "rename", attempt)
    identity = publish(writer)
    assert attempts == [32]
    assert writer.read_package(identity)["package_state"] == "PACKAGE_COMPLETE"
