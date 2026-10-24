"""Explicit test doubles and native recorder fixtures, no strategy monkeypatching."""

from __future__ import annotations

import ctypes
import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from typing import Any

import numpy as np

from sq04c_harness.config import HarnessConfig
from sq04c_harness.metrics import Metrics
from sq04c_harness.reconcile import Census, Reconciliation, reconcile
from sq04c_harness.supervisor import Supervisor


def s9_r3_frames(scenario: str) -> tuple[Any, ...]:
    """Input pixels only; no signal, acceptance, evaluation or exit is injected.

    Thirty closed white bodies plus a latest body: x=20+18*i, width=11,
    y=400-close through y+12 inclusive. No wicks/labels/price or real instrument.
    Levels are deliberately synthetic (gaps allowed), not market evidence.
    """
    from sq04c_harness.composition import SyntheticFrame

    closes = [100 + 8 * i for i in range(20)] + [
        244,
        252,
        260,
        252,
        276,
        264,
        252,
        240,
        232,
        256,
        264,
    ]
    pixels: np.ndarray[Any, np.dtype[np.uint8]] = np.zeros(
        (400, 640, 3), dtype=np.uint8
    )
    if scenario != "none":
        for index, close in enumerate(closes):
            x, y = 20 + 18 * index, 400 - close
            pixels[y : y + 13, x : x + 11] = 255
    seconds = (0, 12) if scenario == "accredited" else (0, 9, 12)
    start = datetime(2026, 1, 1, tzinfo=UTC)

    def marked_pixels(index: int) -> np.ndarray:
        image = pixels.copy()
        image[0, 0] = (index + 1, 0, 0)  # Dark input marker, not candle/price data.
        return image

    return tuple(
        SyntheticFrame(
            image=marked_pixels(index),
            frame_id=index + 1,
            created_at=start + timedelta(seconds=second),
            monotonic_timestamp_ns=second * 1_000_000_000,
            instrument_context_image=(
                np.zeros((2, 2, 3), dtype=np.uint8)
                if scenario == "missing" and second == 9
                else None
            ),
        )
        for index, second in enumerate(seconds)
    )


class FakeWriter:
    queued_items = 0
    queued_bytes = 0
    failure_count = 0
    lost_event_count = 0
    last_error: str | None = None
    last_write_seconds: float | None = None
    flush_value = True
    flush_error = False
    flush_calls = 0
    retry_calls = 0

    def flush(self, timeout: float) -> bool:
        self.flush_calls += 1
        if self.flush_error:
            raise OSError("synthetic flush exception")
        return self.flush_value

    def retry_failed(self, acceptance_id: str) -> int:
        self.retry_calls += 1
        self.queued_items = self.queued_bytes = 0
        self.flush_value = True
        return 1


class FakeLoop:
    def __init__(self) -> None:
        self.started = self.stopped = self.cycles = self.stop_requests = 0
        self.entered, self.release = Event(), Event()
        self.block = False
        self.cycle_error: str | None = None
        self.close_error = False

    def start_session(self) -> bool:
        self.started += 1
        return self.started == 1

    def run_once(self) -> object:
        self.entered.set()
        if self.block:
            self.release.wait()  # Every blocking test releases this in finally.
        self.cycles += 1
        if self.cycle_error:
            raise OSError(self.cycle_error)
        return object()

    def stop(self) -> None:
        self.stop_requests += 1

    def stop_session(self) -> None:
        self.stopped += 1
        if self.close_error:
            raise OSError("synthetic session close exception")


def make_supervisor(
    loop: FakeLoop | None = None,
    writer: FakeWriter | None = None,
    reconciliation: Reconciliation | None = None,
) -> Supervisor:
    loop = loop or FakeLoop()
    writer = writer or FakeWriter()
    record = reconciliation or Reconciliation(True, {}, [], [], {}, 0, "SYNTHETIC")
    return Supervisor(
        pipeline=object(),
        recorder=SimpleNamespace(pending_count=0),
        writer=writer,
        analysis=object(),
        loop=loop,
        runtime=object(),
        reconcile=lambda: record,
        metrics=Metrics(16),
        interval=0,
        max_cycles=2,
        known_acceptances=lambda: {"synthetic-acceptance", "id"},
    )


def finished(supervisor: Supervisor) -> None:
    supervisor.start()
    assert supervisor.done.wait(2), "Synthetic worker failed to complete"


class NativePackage:
    def __init__(self, config: HarnessConfig) -> None:
        from pocket_option_analyzer.application.evidence.observational_evidence import (
            ObservationalEvidenceRecorder,
        )
        from pocket_option_analyzer.application.signals.accepted_signal_evidence import (  # noqa: E501
            AcceptedSignalEvidenceRecorder,
        )
        from pocket_option_analyzer.infrastructure.evidence.observational_evidence_writer import (  # noqa: E501
            ObservationalEvidenceWriter,
        )

        self.config = config
        self.writer = ObservationalEvidenceWriter(config.validate(), background=False)
        self.recorder = ObservationalEvidenceRecorder(config.validate(), self.writer)
        self.native = AcceptedSignalEvidenceRecorder()
        self.census = Census()
        self.start = datetime(2026, 1, 1, tzinfo=UTC)
        config.sq03.mkdir()
        evaluation, frame = self.frame(0, 1)
        record = SimpleNamespace(
            signal=SimpleNamespace(direction=SimpleNamespace(value="call")),
            disposition=SimpleNamespace(value="actionable_accepted"),
            candle_interval_started_at=self.start,
        )
        self.acceptance = self.native.accept(
            evaluation,
            record,
            self.start,
            memory_only=True,
        )
        self.identity = self.acceptance.acceptance_id
        self.census.acceptance(self.acceptance.to_dict())
        self.append(
            config.sq03 / "signals.jsonl",
            {
                "accepted_evidence": self.acceptance.to_dict(),
            },
        )
        self.recorder.accepted(self.acceptance, frame)
        self.writer.drain()

    @staticmethod
    def append(path: Path, value: Any) -> None:
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(value) + "\n")

    def frame(self, seconds: int, frame_id: int) -> tuple[Any, Any]:
        observed = self.start + timedelta(seconds=seconds)
        payload = {
            "observed_at": observed.isoformat(),
            "frame_id": frame_id,
            "source": "synthetic",
            "source_key": "SYNTHETIC_NO_SCREEN",
            "session_key": "synthetic-session",
        }
        evaluation = self.native.capture(observed, payload)
        self.census.evaluation(evaluation.to_dict())
        frame = self.recorder.capture(
            np.full((8, 8, 3), frame_id, dtype=np.uint8),
            None,
            None,
            evaluation.to_dict(),
        )
        return evaluation, frame

    def complete(self) -> None:
        evaluation, frame = self.frame(9, 2)
        self.recorder.observed(evaluation, frame, ())
        evaluation, frame = self.frame(12, 3)
        selected = self.native.observe_exits(evaluation)
        for exit_record in selected:
            self.append(self.config.sq03 / "observations.jsonl", exit_record.to_dict())
        self.recorder.observed(evaluation, frame, selected)
        self.recorder.stop_session()
        self.writer.drain()
        assert self.writer.flush(0)

    def partial(self) -> None:
        self.recorder.stop_session()
        self.writer.drain()
        assert self.writer.flush(0)


def native_supervisor(fixture: NativePackage) -> Supervisor:
    """Fake acquisition only; real recorder, writer and disk reconciliation."""
    return Supervisor(
        pipeline=object(),
        recorder=fixture.recorder,
        writer=fixture.writer,
        analysis=object(),
        loop=FakeLoop(),
        runtime=object(),
        reconcile=lambda: reconcile(
            fixture.writer, fixture.census, fixture.config.sq03
        ),
        metrics=Metrics(16),
        interval=0,
        max_cycles=1,
        known_acceptances=lambda: set(fixture.census.acceptances),
    )


@contextmanager
def exclusive_fixture_read(path: Path) -> Iterator[None]:
    """Real Windows sharing violation, limited to an existing synthetic fixture."""
    from ctypes import wintypes

    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.CreateFileW.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    api.CreateFileW.restype = wintypes.HANDLE
    api.CloseHandle.argtypes = (wintypes.HANDLE,)
    api.CloseHandle.restype = wintypes.BOOL
    handle = api.CreateFileW(str(path), 0x80000000, 0, None, 3, 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        yield
    finally:
        if not api.CloseHandle(handle):
            raise ctypes.WinError(ctypes.get_last_error())
