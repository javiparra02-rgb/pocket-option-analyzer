from __future__ import annotations

import pytest

from pocket_option_analyzer.infrastructure.windows import (
    WindowsWindowCaptureExcluder,
)


def test_window_capture_excluder_applies_exclude_from_capture() -> None:

    calls: list[
        tuple[
            int,
            int,
        ]
    ] = []

    def set_affinity(
        window_handle: int,
        affinity: int,
    ) -> bool:
        calls.append(
            (
                window_handle,
                affinity,
            )
        )
        return True

    excluder = WindowsWindowCaptureExcluder(
        set_window_display_affinity=set_affinity,
        platform_name="win32",
    )

    result = excluder.exclude(
        window_handle=12345,
    )

    assert result is True
    assert calls == [
        (
            12345,
            WindowsWindowCaptureExcluder.WDA_EXCLUDEFROMCAPTURE,
        ),
    ]
    assert excluder.last_error_code is None


def test_window_capture_excluder_preserves_win32_error_code() -> None:

    excluder = WindowsWindowCaptureExcluder(
        set_window_display_affinity=(
            lambda window_handle, affinity: False
        ),
        last_error_reader=lambda: 5,
        platform_name="win32",
    )

    result = excluder.exclude(
        window_handle=12345,
    )

    assert result is False
    assert excluder.last_error_code == 5


def test_window_capture_excluder_rejects_invalid_handle() -> None:

    excluder = WindowsWindowCaptureExcluder(
        set_window_display_affinity=(
            lambda window_handle, affinity: True
        ),
        platform_name="win32",
    )

    with pytest.raises(
        ValueError,
        match="window_handle debe ser mayor que cero",
    ):
        excluder.exclude(
            window_handle=0,
        )


def test_window_capture_excluder_does_not_call_win32_outside_windows() -> None:

    calls = 0

    def unexpected_setter(
        window_handle: int,
        affinity: int,
    ) -> bool:
        nonlocal calls
        calls += 1
        return True

    excluder = WindowsWindowCaptureExcluder(
        set_window_display_affinity=unexpected_setter,
        platform_name="linux",
    )

    result = excluder.exclude(
        window_handle=12345,
    )

    assert result is False
    assert calls == 0
    assert excluder.last_error_code is None