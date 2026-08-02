from pocket_option_analyzer.infrastructure.capture.adapters import (
    Win32WindowLocator,
)


def test_locator_creation() -> None:
    locator = Win32WindowLocator()

    assert locator is not None
