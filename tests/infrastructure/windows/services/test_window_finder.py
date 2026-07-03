from pocket_option_analyzer.infrastructure.windows.models import (
    Win32WindowInfo,
)
from pocket_option_analyzer.infrastructure.windows.services import (
    WindowFinder,
)


class FakeEnumerator:

    def enumerate(self):

        return [

            Win32WindowInfo(
                hwnd=1,
                title="Chrome",
            ),

            Win32WindowInfo(
                hwnd=2,
                title="Pocket Option",
            ),
        ]


def test_find_returns_window():

    finder = WindowFinder(FakeEnumerator())

    result = finder.find("Pocket")

    assert result is not None

    assert result.hwnd == 2