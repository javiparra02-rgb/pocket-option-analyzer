from __future__ import annotations

import numpy as np
import pytest

from pocket_option_analyzer.infrastructure.capture import (
    CaptureUnavailableError,
)
from pocket_option_analyzer.infrastructure.capture.adapters import (
    MSSCaptureAdapter,
    mss_capture_adapter,
)
from pocket_option_analyzer.infrastructure.capture.models import (
    WindowInfo,
)


class FakeMSS:
    def __init__(
        self,
        screenshot: np.ndarray,
        error: Exception | None = None,
    ) -> None:
        self._screenshot = screenshot
        self._error = error

        self.entered = False
        self.closed = False
        self.monitor: dict[str, int] | None = None

    def __enter__(
        self,
    ) -> FakeMSS:
        self.entered = True
        return self

    def __exit__(
        self,
        exception_type,
        exception_value,
        traceback,
    ) -> bool:
        self.closed = True
        return False

    def grab(
        self,
        monitor: dict[str, int],
    ) -> np.ndarray:
        self.monitor = monitor

        if self._error is not None:
            raise self._error

        return self._screenshot


def _window() -> WindowInfo:

    return WindowInfo(
        title="Pocket Option",
        left=-120,
        top=40,
        width=4,
        height=3,
    )


def test_adapter_creation() -> None:

    adapter = MSSCaptureAdapter()

    assert adapter is not None


def test_adapter_closes_mss_and_returns_independent_image(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:

    screenshot = np.arange(
        3 * 4 * 4,
        dtype=np.uint8,
    ).reshape(
        3,
        4,
        4,
    )

    fake_mss = FakeMSS(
        screenshot=screenshot,
    )

    monkeypatch.setattr(
        mss_capture_adapter.mss,
        "MSS",
        lambda: fake_mss,
    )

    adapter = MSSCaptureAdapter()

    result = adapter.capture(
        window=_window(),
    )

    assert fake_mss.entered is True
    assert fake_mss.closed is True

    assert fake_mss.monitor == {
        "left": -120,
        "top": 40,
        "width": 4,
        "height": 3,
    }

    assert np.array_equal(
        result,
        screenshot,
    )

    assert not np.shares_memory(
        result,
        screenshot,
    )

    screenshot.fill(
        0,
    )

    assert np.any(
        result != 0,
    )

    captured_output = capsys.readouterr()

    assert captured_output.out == ""
    assert captured_output.err == ""


def test_adapter_closes_mss_when_capture_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:

    fake_mss = FakeMSS(
        screenshot=np.zeros(
            (3, 4, 4),
            dtype=np.uint8,
        ),
        error=RuntimeError(
            "capture failed",
        ),
    )

    monkeypatch.setattr(
        mss_capture_adapter.mss,
        "MSS",
        lambda: fake_mss,
    )

    adapter = MSSCaptureAdapter()

    with pytest.raises(
        RuntimeError,
        match="capture failed",
    ):
        adapter.capture(
            window=_window(),
        )

    assert fake_mss.entered is True
    assert fake_mss.closed is True


def test_adapter_translates_screenshot_error_to_capture_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:

    screenshot_error = mss_capture_adapter.mss.ScreenShotError(
        "screen pixels unavailable",
    )

    fake_mss = FakeMSS(
        screenshot=np.zeros(
            (3, 4, 4),
            dtype=np.uint8,
        ),
        error=screenshot_error,
    )

    monkeypatch.setattr(
        mss_capture_adapter.mss,
        "MSS",
        lambda: fake_mss,
    )

    adapter = MSSCaptureAdapter()

    with pytest.raises(
        CaptureUnavailableError,
        match="MSS could not capture",
    ) as captured_error:
        adapter.capture(
            window=_window(),
        )

    assert fake_mss.entered is True
    assert fake_mss.closed is True
    assert captured_error.value.__cause__ is (screenshot_error)


def test_adapter_translates_screenshot_error_during_mss_creation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:

    screenshot_error = mss_capture_adapter.mss.ScreenShotError(
        "capture backend unavailable",
    )

    def fail_mss_creation():
        raise screenshot_error

    monkeypatch.setattr(
        mss_capture_adapter.mss,
        "MSS",
        fail_mss_creation,
    )

    adapter = MSSCaptureAdapter()

    with pytest.raises(
        CaptureUnavailableError,
        match="MSS could not capture",
    ) as captured_error:
        adapter.capture(
            window=_window(),
        )

    assert captured_error.value.__cause__ is (screenshot_error)
