from __future__ import annotations

from pocket_option_analyzer.infrastructure.windows import (
    NativeWindowSnapshot,
    ScreenRectangle,
    WindowsRecordingSafetyGuard,
)


def _window(
    handle: int,
    title: str,
    left: int,
    top: int,
    right: int,
    bottom: int,
    is_minimized: bool = False,
) -> NativeWindowSnapshot:

    return NativeWindowSnapshot(
        handle=handle,
        title=title,
        rectangle=ScreenRectangle(
            left=left,
            top=top,
            right=right,
            bottom=bottom,
        ),
        is_minimized=is_minimized,
    )


def test_recording_guard_accepts_separated_windows() -> None:

    guard = WindowsRecordingSafetyGuard(
        snapshot_provider=lambda: (
            _window(
                10,
                "Pocket Option Analyzer",
                1200,
                0,
                1600,
                900,
            ),
            _window(
                20,
                "Pocket Option - Trading",
                0,
                0,
                1100,
                900,
            ),
        ),
        platform_name="win32",
    )

    result = guard.check(
        analyzer_window_handle=10,
    )

    assert result.is_safe is True
    assert result.target_title == "Pocket Option - Trading"


def test_recording_guard_rejects_overlapping_windows() -> None:

    guard = WindowsRecordingSafetyGuard(
        snapshot_provider=lambda: (
            _window(
                10,
                "Pocket Option Analyzer",
                900,
                100,
                1400,
                800,
            ),
            _window(
                20,
                "Pocket Option - Trading",
                0,
                0,
                1200,
                900,
            ),
        ),
        platform_name="win32",
    )

    result = guard.check(
        analyzer_window_handle=10,
    )

    assert result.is_safe is False
    assert "se superpone" in result.message


def test_recording_guard_applies_safety_margin() -> None:

    guard = WindowsRecordingSafetyGuard(
        safety_margin_px=8,
        snapshot_provider=lambda: (
            _window(
                10,
                "Pocket Option Analyzer",
                1104,
                0,
                1500,
                900,
            ),
            _window(
                20,
                "Pocket Option - Trading",
                0,
                0,
                1100,
                900,
            ),
        ),
        platform_name="win32",
    )

    result = guard.check(
        analyzer_window_handle=10,
    )

    assert result.is_safe is False


def test_recording_guard_rejects_missing_pocket_option_window() -> None:

    guard = WindowsRecordingSafetyGuard(
        snapshot_provider=lambda: (
            _window(
                10,
                "Pocket Option Analyzer",
                1200,
                0,
                1600,
                900,
            ),
        ),
        platform_name="win32",
    )

    result = guard.check(
        analyzer_window_handle=10,
    )

    assert result.is_safe is False
    assert "No se encontró" in result.message