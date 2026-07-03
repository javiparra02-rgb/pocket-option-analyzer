from pocket_option_analyzer.infrastructure.windows.services import (
    WindowEnumerator,
)
from pocket_option_analyzer.infrastructure.windows.native import (
    User32,
)


def test_can_create_window_enumerator() -> None:
    enumerator = WindowEnumerator(User32())

    assert enumerator is not None