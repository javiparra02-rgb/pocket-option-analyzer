from typing import Protocol

from pocket_option_analyzer.infrastructure.capture.contracts.window_locator import (
    WindowLocator,
)


def test_window_locator_is_protocol() -> None:
    assert issubclass(WindowLocator, Protocol)