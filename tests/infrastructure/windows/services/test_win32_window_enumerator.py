from __future__ import annotations


class FakeUser32:
    def __init__(
        self,
        hwnds: list[int],
    ) -> None:
        self._hwnds = hwnds

    def enum_windows(
        self,
        callback,
    ) -> None:
        for hwnd in self._hwnds:
            callback(
                hwnd,
                0,
            )


from pocket_option_analyzer.infrastructure.windows.services import (  # noqa: E402
    WindowEnumerator,
)


def test_window_enumerator_returns_hwnds_in_native_order() -> None:

    enumerator = WindowEnumerator(
        FakeUser32(
            [
                101,
                202,
                303,
            ]
        )
    )

    result = enumerator.enumerate_hwnds()

    assert result == [
        101,
        202,
        303,
    ]


def test_window_enumerator_ignores_null_handle() -> None:

    enumerator = WindowEnumerator(
        FakeUser32(
            [
                0,
                101,
            ]
        )
    )

    result = enumerator.enumerate_hwnds()

    assert result == [
        101,
    ]
