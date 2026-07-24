from __future__ import annotations

import ctypes
import sys
from collections.abc import Callable

SetWindowDisplayAffinityCallable = Callable[
    [
        int,
        int,
    ],
    bool,
]
LastErrorReader = Callable[[], int]


class WindowsWindowCaptureExcluder:
    """
    Excluye una ventana propia de las capturas de pantalla en Windows.

    Usa WDA_EXCLUDEFROMCAPTURE para impedir que la ventana del
    analizador contamine las imágenes procesadas por visión.

    No oculta la ventana para el usuario.
    No interactúa con Pocket Option.
    """

    WDA_NONE = 0x00000000
    WDA_EXCLUDEFROMCAPTURE = 0x00000011

    def __init__(
        self,
        set_window_display_affinity: (
            SetWindowDisplayAffinityCallable | None
        ) = None,
        last_error_reader: LastErrorReader | None = None,
        platform_name: str | None = None,
    ) -> None:
        self._set_window_display_affinity = (
            set_window_display_affinity
        )
        self._last_error_reader = (
            last_error_reader
            or self._read_last_error
        )
        self._platform_name = (
            platform_name
            if platform_name is not None
            else sys.platform
        )
        self._last_error_code: int | None = None

    @property
    def is_supported(self) -> bool:
        return self._platform_name == "win32"

    @property
    def last_error_code(self) -> int | None:
        return self._last_error_code

    def exclude(
        self,
        window_handle: int,
    ) -> bool:
        """
        Excluye la ventana de capturas de pantalla.
        """

        return self._apply_affinity(
            window_handle=window_handle,
            affinity=self.WDA_EXCLUDEFROMCAPTURE,
        )

    def _resolve_setter(
        self,
    ) -> SetWindowDisplayAffinityCallable:
        if self._set_window_display_affinity is None:
            self._set_window_display_affinity = (
                self._create_native_setter()
            )

        return self._set_window_display_affinity

    @staticmethod
    def _create_native_setter(
    ) -> SetWindowDisplayAffinityCallable:
        """
        Configura la firma nativa de SetWindowDisplayAffinity.
        """

        from ctypes import wintypes

        user32 = ctypes.WinDLL(
            "user32",
            use_last_error=True,
        )

        native_function = (
            user32.SetWindowDisplayAffinity
        )
        native_function.argtypes = [
            wintypes.HWND,
            wintypes.DWORD,
        ]
        native_function.restype = wintypes.BOOL

        def setter(
            window_handle: int,
            affinity: int,
        ) -> bool:
            return bool(
                native_function(
                    window_handle,
                    affinity,
                )
            )

        return setter

    @staticmethod
    def _read_last_error() -> int:
        reader = getattr(
            ctypes,
            "get_last_error",
            None,
        )

        if reader is None:
            return 0

        return int(
            reader()
        )

    def allow_capture(
        self,
        window_handle: int,
    ) -> bool:
        """
        Elimina temporalmente la exclusión de captura.

        Se utiliza únicamente para obtener evidencias visuales mientras
        el análisis continuo está detenido.
        """

        return self._apply_affinity(
            window_handle=window_handle,
            affinity=self.WDA_NONE,
        )

    def _apply_affinity(
        self,
        window_handle: int,
        affinity: int,
    ) -> bool:
        self._last_error_code = None

        if not self.is_supported:
            return False

        if window_handle <= 0:
            raise ValueError(
                "window_handle debe ser mayor que cero."
            )

        setter = self._resolve_setter()

        was_applied = bool(
            setter(
                window_handle,
                affinity,
            )
        )

        if was_applied:
            return True

        self._last_error_code = int(
            self._last_error_reader()
        )

        return False