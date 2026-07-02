from pocket_option_analyzer.infrastructure.capture.adapters import (
    WindowEnumerator,
)


def test_enumerator_creation() -> None:
    enumerator = WindowEnumerator()

    assert enumerator is not None