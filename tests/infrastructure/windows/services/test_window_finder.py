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
                left=0,
                top=0,
                width=100,
                height=100,
                client_left=0,
                client_top=0,
                client_width=100,
                client_height=100,
                visible=True,
                minimized=False,
            ),
            Win32WindowInfo(
                hwnd=2,
                title="Pocket Option",
                left=100,
                top=100,
                width=1200,
                height=800,
                client_left=108,
                client_top=132,
                client_width=1184,
                client_height=760,
                visible=True,
                minimized=False,
            ),
        ]


def test_find_returns_window():

    finder = WindowFinder(FakeEnumerator())

    result = finder.find("Pocket")

    assert result is not None

    assert result.hwnd == 2
