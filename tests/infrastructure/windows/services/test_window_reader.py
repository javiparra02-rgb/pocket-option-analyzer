from __future__ import annotations

import pytest

from pocket_option_analyzer.infrastructure.capture import (
    CaptureUnavailableError,
)
from pocket_option_analyzer.infrastructure.windows.models import (
    Win32WindowInfo,
)
from pocket_option_analyzer.infrastructure.windows.native import (
    POINT,
    RECT,
)
from pocket_option_analyzer.infrastructure.windows.services.window_reader import (
    WindowReader,
)


class FakeUser32:
    def __init__(
        self,
    ) -> None:
        self.window_exists = True
        self.visible = True
        self.minimized = False
        self.title = "Pocket Option"

        self.window_rect = RECT(
            0,
            0,
            100,
            100,
        )

        self.client_rect = RECT(
            0,
            0,
            80,
            80,
        )

        self.raise_native_error = False

        self.requested_client_origin: tuple[int, int] | None = None

    def is_window(
        self,
        hwnd: int,
    ) -> bool:
        del hwnd

        return self.window_exists

    def get_window_text(
        self,
        hwnd: int,
    ) -> str:
        del hwnd

        return self.title

    def get_window_rect(
        self,
        hwnd: int,
    ) -> RECT:
        del hwnd

        if self.raise_native_error:
            raise OSError("GetWindowRect failed.")

        return self.window_rect

    def get_client_rect(
        self,
        hwnd: int,
    ) -> RECT:
        del hwnd

        return self.client_rect

    def client_to_screen(
        self,
        hwnd: int,
        point: POINT,
    ) -> POINT:
        del hwnd

        self.requested_client_origin = (
            point.x,
            point.y,
        )

        return POINT(
            10,
            20,
        )

    def is_window_visible(
        self,
        hwnd: int,
    ) -> bool:
        del hwnd

        return self.visible

    def is_iconic(
        self,
        hwnd: int,
    ) -> bool:
        del hwnd

        return self.minimized


class FakeFactory:
    def create(
        self,
        **kwargs,
    ) -> Win32WindowInfo:
        return Win32WindowInfo(
            **kwargs,
        )


def test_window_reader_builds_window_info() -> None:

    user32 = FakeUser32()

    reader = WindowReader(
        user32,
        FakeFactory(),
    )

    result = reader.read(
        123,
    )

    assert isinstance(
        result,
        Win32WindowInfo,
    )

    assert result.hwnd == 123
    assert result.title == "Pocket Option"

    assert result.left == 0
    assert result.top == 0
    assert result.width == 100
    assert result.height == 100

    assert result.client_left == 10
    assert result.client_top == 20
    assert result.client_width == 80
    assert result.client_height == 80

    assert result.visible is True
    assert result.minimized is False
    assert result.is_capture_candidate is True

    assert user32.requested_client_origin == (
        0,
        0,
    )


@pytest.mark.parametrize(
    "hwnd",
    [
        0,
        -1,
    ],
)
def test_window_reader_rejects_invalid_handle(
    hwnd: int,
) -> None:

    reader = WindowReader(
        FakeUser32(),
        FakeFactory(),
    )

    with pytest.raises(
        ValueError,
        match="must be greater than zero",
    ):
        reader.read(
            hwnd,
        )


def test_window_reader_rejects_missing_window() -> None:

    user32 = FakeUser32()
    user32.window_exists = False

    reader = WindowReader(
        user32,
        FakeFactory(),
    )

    with pytest.raises(
        CaptureUnavailableError,
        match="no longer exists",
    ):
        reader.read(
            123,
        )


@pytest.mark.parametrize(
    (
        "visible",
        "minimized",
    ),
    [
        (
            False,
            False,
        ),
        (
            True,
            True,
        ),
    ],
    ids=[
        "hidden",
        "minimized",
    ],
)
def test_window_reader_rejects_unavailable_window_state(
    visible: bool,
    minimized: bool,
) -> None:

    user32 = FakeUser32()
    user32.visible = visible
    user32.minimized = minimized

    reader = WindowReader(
        user32,
        FakeFactory(),
    )

    with pytest.raises(
        CaptureUnavailableError,
        match="not available for capture",
    ):
        reader.read(
            123,
        )


def test_window_reader_rejects_empty_title() -> None:

    user32 = FakeUser32()
    user32.title = "   "

    reader = WindowReader(
        user32,
        FakeFactory(),
    )

    with pytest.raises(
        CaptureUnavailableError,
        match="title is empty",
    ):
        reader.read(
            123,
        )


def test_window_reader_translates_native_failure() -> None:

    user32 = FakeUser32()
    user32.raise_native_error = True

    reader = WindowReader(
        user32,
        FakeFactory(),
    )

    with pytest.raises(
        CaptureUnavailableError,
        match="Could not read Win32 window information",
    ) as error_info:
        reader.read(
            123,
        )

    assert isinstance(
        error_info.value.__cause__,
        OSError,
    )


@pytest.mark.parametrize(
    "window_rect",
    [
        RECT(
            0,
            0,
            0,
            100,
        ),
        RECT(
            0,
            0,
            100,
            0,
        ),
    ],
    ids=[
        "zero_width",
        "zero_height",
    ],
)
def test_window_reader_rejects_invalid_window_geometry(
    window_rect: RECT,
) -> None:

    user32 = FakeUser32()
    user32.window_rect = window_rect

    reader = WindowReader(
        user32,
        FakeFactory(),
    )

    with pytest.raises(
        CaptureUnavailableError,
        match="invalid capture geometry",
    ):
        reader.read(
            123,
        )
