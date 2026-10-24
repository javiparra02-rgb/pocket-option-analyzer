"""Bounded, identical OFF/ON instrumentation; synthetic timings are labelled."""

from __future__ import annotations

import ctypes
import os
from collections import deque
from dataclasses import dataclass, field
from math import ceil
from threading import Lock
from time import process_time
from typing import Any


def process_sample() -> dict[str, Any]:
    result: dict[str, Any] = {
        "cpu_seconds": process_time(),
        "rss_bytes": None,
        "process_write_bytes": None,
    }
    if os.name != "nt":
        result["counter_status"] = "WINDOWS_COUNTERS_UNAVAILABLE"
        return result

    from ctypes import wintypes

    class Memory(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
            (name, ctypes.c_size_t)
            for name in (
                "peak_working_set",
                "working_set",
                "peak_paged",
                "paged",
                "peak_nonpaged",
                "nonpaged",
                "pagefile",
                "peak_pagefile",
            )
        ]

    class IO(ctypes.Structure):
        _fields_ = [
            (name, ctypes.c_ulonglong)
            for name in (
                "read_ops",
                "write_ops",
                "other_ops",
                "read_bytes",
                "write_bytes",
                "other_bytes",
            )
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.GetProcessIoCounters.argtypes = [wintypes.HANDLE, ctypes.POINTER(IO)]
    kernel.GetProcessIoCounters.restype = wintypes.BOOL
    psapi.GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(Memory),
        wintypes.DWORD,
    ]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    handle = kernel.GetCurrentProcess()
    memory = Memory()
    memory.cb = ctypes.sizeof(memory)
    io = IO()
    memory_ok = psapi.GetProcessMemoryInfo(handle, ctypes.byref(memory), memory.cb)
    io_ok = kernel.GetProcessIoCounters(handle, ctypes.byref(io))
    if memory_ok:
        result["rss_bytes"] = memory.working_set
    if io_ok:
        result["process_write_bytes"] = io.write_bytes
    result["counter_status"] = "OK" if memory_ok and io_ok else "PARTIAL_UNAVAILABLE"
    return result


def summary(values: list[float]) -> dict[str, float | None]:
    ordered = sorted(values)
    if not ordered:
        return {"p50": None, "p95": None, "max": None}
    return {
        "p50": ordered[ceil(len(ordered) * 0.5) - 1],
        "p95": ordered[ceil(len(ordered) * 0.95) - 1],
        "max": ordered[-1],
    }


@dataclass
class Metrics:
    capacity: int
    cycles: int = 0
    evaluations: int = 0
    errors: int = 0
    queue_max_items: int = 0
    queue_max_bytes: int = 0
    samples: deque[dict[str, Any]] = field(init=False)
    durations: deque[float] = field(init=False)
    intervals: deque[float] = field(init=False)
    lock: Lock = field(default_factory=Lock, repr=False)
    last_start: float | None = None

    def __post_init__(self) -> None:
        self.samples = deque(maxlen=self.capacity)
        self.durations = deque(maxlen=self.capacity)
        self.intervals = deque(maxlen=self.capacity)

    def cycle(
        self, started: float, elapsed: float, evaluated: bool, error: bool
    ) -> None:
        with self.lock:
            if self.last_start is not None:
                self.intervals.append(started - self.last_start)
            self.last_start = started
            self.cycles += 1
            self.evaluations += int(evaluated)
            self.errors += int(error)
            self.durations.append(elapsed)

    def sample(self, writer: dict[str, Any]) -> None:
        sample = {**process_sample(), **writer}
        with self.lock:
            self.samples.append(sample)
            self.queue_max_items = max(self.queue_max_items, writer["queued_items"])
            self.queue_max_bytes = max(self.queue_max_bytes, writer["queued_bytes"])

    def report(self) -> dict[str, Any]:
        with self.lock:
            return {
                "measurement_scope": "SYNTHETIC_NOT_LIVE_PERFORMANCE",
                "percentile_method": "nearest_rank",
                "cycle_seconds": summary(list(self.durations)),
                "interval_seconds": summary(list(self.intervals)),
                "cycles": self.cycles,
                "evaluations": self.evaluations,
                "errors": self.errors,
                "samples": list(self.samples),
                "queue_max_items_observed": self.queue_max_items,
                "queue_max_bytes_observed": self.queue_max_bytes,
                "sample_capacity": self.capacity,
                "queue_max_is_sampled_not_exact_peak": True,
                "physical_device_write_bytes": None,
            }
