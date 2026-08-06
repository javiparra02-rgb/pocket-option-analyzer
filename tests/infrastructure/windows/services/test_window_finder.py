from __future__ import annotations

from pocket_option_analyzer.infrastructure.errors import (
    CaptureUnavailableError,
)
from pocket_option_analyzer.infrastructure.windows.models import (
    Win32WindowInfo,
)
from pocket_option_analyzer.infrastructure.windows.services import (
    WindowFinder,
)


def _window(
    *,
    hwnd: int,
    title: str,
    width: int = 100,
    height: int = 100,
    visible: bool = True,
    minimized: bool = False,
) -> Win32WindowInfo:

    return Win32WindowInfo(
        hwnd=hwnd,
        title=title,
        left=0,
        top=0,
        width=width,
        height=height,
        client_left=0,
        client_top=0,
        client_width=width,
        client_height=height,
        visible=visible,
        minimized=minimized,
    )


class FakeEnumerator:
    def __init__(
        self,
        hwnds: list[int],
    ) -> None:
        self._hwnds = hwnds
        self.calls = 0

    def enumerate_hwnds(
        self,
    ) -> list[int]:
        self.calls += 1

        return list(
            self._hwnds,
        )


class FakeReader:
    def __init__(
        self,
        windows: dict[
            int,
            Win32WindowInfo | Exception,
        ],
    ) -> None:
        self._windows = windows
        self.read_hwnds: list[int] = []

    def read(
        self,
        hwnd: int,
    ) -> Win32WindowInfo:
        self.read_hwnds.append(
            hwnd,
        )

        result = self._windows[hwnd]

        if isinstance(
            result,
            Exception,
        ):
            raise result

        return result


def test_window_finder_returns_largest_matching_capture_candidate() -> None:

    enumerator = FakeEnumerator(
        [
            1,
            2,
            3,
        ]
    )

    reader = FakeReader(
        {
            1: _window(
                hwnd=1,
                title="Pocket Option Small",
                width=800,
                height=600,
            ),
            2: _window(
                hwnd=2,
                title="Chrome",
                width=2000,
                height=1200,
            ),
            3: _window(
                hwnd=3,
                title="POCKET OPTION Main",
                width=1600,
                height=900,
            ),
        }
    )

    finder = WindowFinder(
        enumerator=enumerator,
        reader=reader,
    )

    result = finder.find(
        "pocket option",
    )

    assert result is not None
    assert result.hwnd == 3
    assert result.area == 1_440_000


def test_window_finder_skips_temporarily_unavailable_candidate() -> None:

    enumerator = FakeEnumerator(
        [
            1,
            2,
        ]
    )

    reader = FakeReader(
        {
            1: CaptureUnavailableError("Window disappeared."),
            2: _window(
                hwnd=2,
                title="Pocket Option",
                width=1200,
                height=800,
            ),
        }
    )

    finder = WindowFinder(
        enumerator=enumerator,
        reader=reader,
    )

    result = finder.find(
        "Pocket Option",
    )

    assert result is not None
    assert result.hwnd == 2


def test_window_finder_ignores_non_capture_candidate() -> None:

    enumerator = FakeEnumerator(
        [
            1,
            2,
        ]
    )

    reader = FakeReader(
        {
            1: _window(
                hwnd=1,
                title="Pocket Option Hidden",
                width=2000,
                height=1200,
                visible=False,
            ),
            2: _window(
                hwnd=2,
                title="Pocket Option",
                width=1000,
                height=700,
            ),
        }
    )

    finder = WindowFinder(
        enumerator=enumerator,
        reader=reader,
    )

    result = finder.find(
        "Pocket Option",
    )

    assert result is not None
    assert result.hwnd == 2


def test_window_finder_rejects_empty_search_without_enumerating() -> None:

    enumerator = FakeEnumerator(
        [
            1,
        ]
    )

    reader = FakeReader(
        {
            1: _window(
                hwnd=1,
                title="Pocket Option",
            ),
        }
    )

    finder = WindowFinder(
        enumerator=enumerator,
        reader=reader,
    )

    result = finder.find(
        "   ",
    )

    assert result is None
    assert enumerator.calls == 0
    assert reader.read_hwnds == []


def test_window_finder_returns_none_when_title_does_not_match() -> None:

    finder = WindowFinder(
        enumerator=FakeEnumerator(
            [
                1,
            ]
        ),
        reader=FakeReader(
            {
                1: _window(
                    hwnd=1,
                    title="Visual Studio Code",
                ),
            }
        ),
    )

    result = finder.find(
        "Pocket Option",
    )

    assert result is None


def test_window_finder_find_first_uses_capture_candidates() -> None:

    finder = WindowFinder(
        enumerator=FakeEnumerator(
            [
                1,
                2,
            ]
        ),
        reader=FakeReader(
            {
                1: _window(
                    hwnd=1,
                    title="Chrome",
                ),
                2: _window(
                    hwnd=2,
                    title="Pocket Option",
                ),
            }
        ),
    )

    result = finder.find_first(lambda window: "Pocket" in window.title)

    assert result is not None
    assert result.hwnd == 2
