import pytest

from pocket_option_analyzer.infrastructure.capture.window_locator import (
    WindowLocator,
)


def test_window_locator_not_implemented() -> None:
    locator = WindowLocator()

    with pytest.raises(NotImplementedError):
        locator.find("Pocket Option")