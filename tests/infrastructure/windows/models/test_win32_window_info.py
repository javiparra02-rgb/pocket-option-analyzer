import pytest

from pocket_option_analyzer.infrastructure.windows.models import (
    Win32WindowInfo,
)


def _window_info(
    **overrides: object,
) -> Win32WindowInfo:

    values = {
        "hwnd": 123,
        "title": "Pocket Option",
        "left": 10,
        "top": 20,
        "width": 300,
        "height": 200,
        "client_left": 18,
        "client_top": 52,
        "client_width": 284,
        "client_height": 160,
        "visible": True,
        "minimized": False,
    }

    values.update(
        overrides,
    )

    return Win32WindowInfo(
        **values,
    )


def test_win32_window_info_exposes_derived_geometry() -> None:

    window = _window_info()

    assert window.right == 310
    assert window.bottom == 220
    assert window.area == 60_000
    assert window.is_capture_candidate is True


def test_win32_window_info_accepts_negative_screen_coordinates() -> None:

    window = _window_info(
        left=-1920,
        top=-120,
        width=1600,
        height=900,
    )

    assert window.left == -1920
    assert window.top == -120
    assert window.right == -320
    assert window.bottom == 780
    assert window.area == 1_440_000
    assert window.is_capture_candidate is True


@pytest.mark.parametrize(
    "overrides",
    [
        {
            "hwnd": 0,
        },
        {
            "title": "   ",
        },
        {
            "width": 0,
        },
        {
            "height": -1,
        },
        {
            "visible": False,
        },
        {
            "minimized": True,
        },
    ],
    ids=[
        "invalid_handle",
        "empty_title",
        "zero_width",
        "negative_height",
        "hidden",
        "minimized",
    ],
)
def test_win32_window_info_rejects_non_capture_candidates(
    overrides: dict[str, object],
) -> None:

    window = _window_info(
        **overrides,
    )

    assert window.is_capture_candidate is False
