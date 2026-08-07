from pocket_option_analyzer.infrastructure.capture.contracts import (
    CaptureRegion,
)
from pocket_option_analyzer.infrastructure.windows.models import (
    Win32WindowInfo,
)


def test_win32_window_info_satisfies_capture_region_contract() -> None:

    window = Win32WindowInfo(
        hwnd=123,
        title="Pocket Option",
        left=-1920,
        top=40,
        width=1600,
        height=900,
        client_left=-1912,
        client_top=72,
        client_width=1584,
        client_height=860,
        visible=True,
        minimized=False,
    )

    assert isinstance(
        window,
        CaptureRegion,
    )
