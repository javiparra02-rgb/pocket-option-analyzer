from pocket_option_analyzer.infrastructure.capture.adapters import (
    MSSCaptureAdapter,
)


def test_adapter_creation() -> None:
    adapter = MSSCaptureAdapter()

    assert adapter is not None
