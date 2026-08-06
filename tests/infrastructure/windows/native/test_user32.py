# ruff: noqa: N802

from __future__ import annotations

import ctypes

import pytest

from pocket_option_analyzer.infrastructure.windows.native import (
    POINT,
    RECT,
    User32,
)


class FakeUser32Dll:
    def __init__(
        self,
    ) -> None:
        self.title = "Pocket Option"

        self.window_text_succeeds = True
        self.window_rect_succeeds = True
        self.client_rect_succeeds = True
        self.client_to_screen_succeeds = True

    def IsWindow(
        self,
        hwnd: int,
    ) -> int:
        del hwnd

        return 1

    def IsWindowVisible(
        self,
        hwnd: int,
    ) -> int:
        del hwnd

        return 1

    def IsIconic(
        self,
        hwnd: int,
    ) -> int:
        del hwnd

        return 0

    def GetWindowTextLengthW(
        self,
        hwnd: int,
    ) -> int:
        del hwnd

        return len(
            self.title,
        )

    def GetWindowTextW(
        self,
        hwnd: int,
        buffer,
        buffer_length: int,
    ) -> int:
        del hwnd

        if not self.window_text_succeeds:
            return 0

        buffer.value = self.title[: buffer_length - 1]

        return len(
            buffer.value,
        )

    def GetWindowRect(
        self,
        hwnd: int,
        rect_pointer,
    ) -> int:
        del hwnd

        if not self.window_rect_succeeds:
            return 0

        rect = ctypes.cast(
            rect_pointer,
            ctypes.POINTER(
                RECT,
            ),
        ).contents

        rect.left = -10
        rect.top = 20
        rect.right = 290
        rect.bottom = 220

        return 1

    def GetClientRect(
        self,
        hwnd: int,
        rect_pointer,
    ) -> int:
        del hwnd

        if not self.client_rect_succeeds:
            return 0

        rect = ctypes.cast(
            rect_pointer,
            ctypes.POINTER(
                RECT,
            ),
        ).contents

        rect.left = 0
        rect.top = 0
        rect.right = 280
        rect.bottom = 160

        return 1

    def ClientToScreen(
        self,
        hwnd: int,
        point_pointer,
    ) -> int:
        del hwnd

        if not self.client_to_screen_succeeds:
            return 0

        point = ctypes.cast(
            point_pointer,
            ctypes.POINTER(
                POINT,
            ),
        ).contents

        point.x = 8
        point.y = 52

        return 1


def test_user32_reads_window_information() -> None:

    api = User32(
        dll=FakeUser32Dll(),
    )

    assert api.is_window(
        123,
    )

    assert api.is_window_visible(
        123,
    )

    assert not api.is_iconic(
        123,
    )

    assert (
        api.get_window_text(
            123,
        )
        == "Pocket Option"
    )

    window_rect = api.get_window_rect(
        123,
    )

    assert window_rect.left == -10
    assert window_rect.top == 20
    assert window_rect.right == 290
    assert window_rect.bottom == 220

    client_rect = api.get_client_rect(
        123,
    )

    assert client_rect.left == 0
    assert client_rect.top == 0
    assert client_rect.right == 280
    assert client_rect.bottom == 160

    point = api.client_to_screen(
        123,
        POINT(
            0,
            0,
        ),
    )

    assert point.x == 8
    assert point.y == 52


@pytest.mark.parametrize(
    "operation",
    [
        "window_text",
        "window_rect",
        "client_rect",
        "client_to_screen",
    ],
)
def test_user32_raises_when_native_operation_fails(
    operation: str,
) -> None:

    dll = FakeUser32Dll()

    if operation == "window_text":
        dll.window_text_succeeds = False

    elif operation == "window_rect":
        dll.window_rect_succeeds = False

    elif operation == "client_rect":
        dll.client_rect_succeeds = False

    elif operation == "client_to_screen":
        dll.client_to_screen_succeeds = False

    api = User32(
        dll=dll,
    )

    with pytest.raises(
        OSError,
    ):
        if operation == "window_text":
            api.get_window_text(
                123,
            )

        elif operation == "window_rect":
            api.get_window_rect(
                123,
            )

        elif operation == "client_rect":
            api.get_client_rect(
                123,
            )

        else:
            api.client_to_screen(
                123,
                POINT(
                    0,
                    0,
                ),
            )
