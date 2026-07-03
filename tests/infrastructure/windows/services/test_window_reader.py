from pocket_option_analyzer.infrastructure.windows.services.window_reader import (
    WindowReader,
)
from pocket_option_analyzer.infrastructure.windows.models import Win32WindowInfo


class FakeUser32:
    def get_window_text(self, hwnd): return "Pocket Option"
    def get_window_rect(self, hwnd):
        class R: left=0; top=0; right=100; bottom=100
        return R()
    def get_client_rect(self, hwnd):
        class R: left=0; top=0; right=80; bottom=80
        return R()
    def client_to_screen(self, hwnd, point):
        class P: x=10; y=20
        return P()
    def is_window_visible(self, hwnd): return True
    def is_iconic(self, hwnd): return False


class FakeFactory:
    def create(self, **kwargs):
        return Win32WindowInfo(**kwargs)


def test_window_reader_builds_window_info():
    reader = WindowReader(FakeUser32(), FakeFactory())

    result = reader.read(123)

    assert isinstance(result, Win32WindowInfo)
    assert result.title == "Pocket Option"
    assert result.width == 100
    assert result.visible is True