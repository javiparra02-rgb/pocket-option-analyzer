from __future__ import annotations

import ctypes
import sys
from collections.abc import Callable
from ctypes import wintypes
from dataclasses import dataclass


@dataclass(
    frozen=True,
    slots=True,
)
class ScreenRectangle:
    """
    Rectángulo expresado en coordenadas absolutas de pantalla.

    right y bottom siguen la convención Win32: representan el
    límite exterior del rectángulo.
    """

    left: int
    top: int
    right: int
    bottom: int

    def __post_init__(
        self,
    ) -> None:
        if self.right <= self.left:
            raise ValueError("right debe ser mayor que left.")

        if self.bottom <= self.top:
            raise ValueError("bottom debe ser mayor que top.")

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    @property
    def area(self) -> int:
        return self.width * self.height

    def expanded(
        self,
        margin: int,
    ) -> ScreenRectangle:
        """
        Amplía el rectángulo para conservar una separación de seguridad.
        """

        if margin < 0:
            raise ValueError("margin no puede ser negativo.")

        return ScreenRectangle(
            left=self.left - margin,
            top=self.top - margin,
            right=self.right + margin,
            bottom=self.bottom + margin,
        )

    def intersects(
        self,
        other: ScreenRectangle,
    ) -> bool:
        """
        Determina si dos rectángulos comparten área visible.
        """

        return (
            self.left < other.right
            and self.right > other.left
            and self.top < other.bottom
            and self.bottom > other.top
        )


@dataclass(
    frozen=True,
    slots=True,
)
class NativeWindowSnapshot:
    """
    Información mínima de una ventana superior de Windows.
    """

    handle: int
    title: str
    rectangle: ScreenRectangle
    is_visible: bool = True
    is_minimized: bool = False

    def __post_init__(
        self,
    ) -> None:
        if self.handle <= 0:
            raise ValueError("handle debe ser mayor que cero.")


@dataclass(
    frozen=True,
    slots=True,
)
class RecordingSafetyStatus:
    """
    Resultado de comprobar la ubicación para una grabación segura.
    """

    is_safe: bool
    message: str
    analyzer_rectangle: ScreenRectangle | None = None
    target_rectangle: ScreenRectangle | None = None
    target_title: str | None = None


WindowSnapshotProvider = Callable[
    [],
    tuple[NativeWindowSnapshot, ...],
]


class WindowsRecordingSafetyGuard:
    """
    Verifica que el analizador no cubra la ventana de Pocket Option.

    La validación usa coordenadas reales de pantalla obtenidas mediante
    la API Win32. No mueve ni modifica ninguna ventana.
    """

    def __init__(
        self,
        target_title_fragment: str = "Pocket Option",
        safety_margin_px: int = 8,
        snapshot_provider: WindowSnapshotProvider | None = None,
        platform_name: str | None = None,
    ) -> None:
        if not target_title_fragment.strip():
            raise ValueError("target_title_fragment no puede estar vacío.")

        if safety_margin_px < 0:
            raise ValueError("safety_margin_px no puede ser negativo.")

        self._target_title_fragment = target_title_fragment.casefold()
        self._safety_margin_px = safety_margin_px
        self._snapshot_provider = snapshot_provider or self._capture_native_snapshots
        self._platform_name = (
            platform_name if platform_name is not None else sys.platform
        )
        self._last_status: RecordingSafetyStatus | None = None

    @property
    def is_supported(self) -> bool:
        return self._platform_name == "win32"

    @property
    def last_status(
        self,
    ) -> RecordingSafetyStatus | None:
        return self._last_status

    def check(
        self,
        analyzer_window_handle: int,
    ) -> RecordingSafetyStatus:
        """
        Comprueba que el analizador y Pocket Option no se superpongan.
        """

        if analyzer_window_handle <= 0:
            raise ValueError("analyzer_window_handle debe ser mayor que cero.")

        if not self.is_supported:
            return self._store_status(
                RecordingSafetyStatus(
                    is_safe=False,
                    message=(
                        "El modo grabación segura solo está disponible en Windows."
                    ),
                )
            )

        snapshots = self._snapshot_provider()

        analyzer_window = next(
            (
                snapshot
                for snapshot in snapshots
                if snapshot.handle == analyzer_window_handle
            ),
            None,
        )

        if analyzer_window is None:
            return self._store_status(
                RecordingSafetyStatus(
                    is_safe=False,
                    message=(
                        "No se pudo leer la posición de la ventana del analizador."
                    ),
                )
            )

        target_windows = tuple(
            snapshot
            for snapshot in snapshots
            if self._is_target_window(
                snapshot=snapshot,
                analyzer_window_handle=analyzer_window_handle,
            )
        )

        if not target_windows:
            return self._store_status(
                RecordingSafetyStatus(
                    is_safe=False,
                    message=("No se encontró una ventana visible de Pocket Option."),
                    analyzer_rectangle=analyzer_window.rectangle,
                )
            )

        target_window = max(
            target_windows,
            key=lambda snapshot: snapshot.rectangle.area,
        )

        protected_analyzer_rectangle = analyzer_window.rectangle.expanded(
            margin=self._safety_margin_px,
        )

        if protected_analyzer_rectangle.intersects(
            target_window.rectangle,
        ):
            return self._store_status(
                RecordingSafetyStatus(
                    is_safe=False,
                    message=(
                        "El analizador se superpone con Pocket Option. "
                        "Muévelo completamente fuera de la ventana "
                        "del gráfico."
                    ),
                    analyzer_rectangle=analyzer_window.rectangle,
                    target_rectangle=target_window.rectangle,
                    target_title=target_window.title,
                )
            )

        return self._store_status(
            RecordingSafetyStatus(
                is_safe=True,
                message=("Ubicación segura para grabación."),
                analyzer_rectangle=analyzer_window.rectangle,
                target_rectangle=target_window.rectangle,
                target_title=target_window.title,
            )
        )

    def _is_target_window(
        self,
        snapshot: NativeWindowSnapshot,
        analyzer_window_handle: int,
    ) -> bool:
        if snapshot.handle == analyzer_window_handle:
            return False

        if not snapshot.is_visible:
            return False

        if snapshot.is_minimized:
            return False

        normalized_title = snapshot.title.casefold()

        # Evita considerar otra instancia del propio analizador.
        if "pocket option analyzer" in normalized_title:
            return False

        return self._target_title_fragment in normalized_title

    def _store_status(
        self,
        status: RecordingSafetyStatus,
    ) -> RecordingSafetyStatus:
        self._last_status = status
        return status

    @staticmethod
    def _capture_native_snapshots() -> tuple[NativeWindowSnapshot, ...]:
        """
        Enumera ventanas superiores visibles mediante user32.
        """

        user32 = ctypes.WinDLL(
            "user32",
            use_last_error=True,
        )

        enum_windows = user32.EnumWindows
        is_window_visible = user32.IsWindowVisible
        is_iconic = user32.IsIconic
        get_window_text_length = user32.GetWindowTextLengthW
        get_window_text = user32.GetWindowTextW
        get_window_rect = user32.GetWindowRect

        callback_type = ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HWND,
            wintypes.LPARAM,
        )

        enum_windows.argtypes = [
            callback_type,
            wintypes.LPARAM,
        ]
        enum_windows.restype = wintypes.BOOL

        is_window_visible.argtypes = [
            wintypes.HWND,
        ]
        is_window_visible.restype = wintypes.BOOL

        is_iconic.argtypes = [
            wintypes.HWND,
        ]
        is_iconic.restype = wintypes.BOOL

        get_window_text_length.argtypes = [
            wintypes.HWND,
        ]
        get_window_text_length.restype = ctypes.c_int

        get_window_text.argtypes = [
            wintypes.HWND,
            wintypes.LPWSTR,
            ctypes.c_int,
        ]
        get_window_text.restype = ctypes.c_int

        get_window_rect.argtypes = [
            wintypes.HWND,
            ctypes.POINTER(
                wintypes.RECT,
            ),
        ]
        get_window_rect.restype = wintypes.BOOL

        snapshots: list[NativeWindowSnapshot] = []

        @callback_type
        def callback(
            window_handle,
            parameter,
        ) -> bool:
            del parameter

            if not is_window_visible(
                window_handle,
            ):
                return True

            title_length = get_window_text_length(
                window_handle,
            )

            if title_length <= 0:
                return True

            title_buffer = ctypes.create_unicode_buffer(
                title_length + 1,
            )

            get_window_text(
                window_handle,
                title_buffer,
                len(
                    title_buffer,
                ),
            )

            title = title_buffer.value.strip()

            if not title:
                return True

            native_rectangle = wintypes.RECT()

            if not get_window_rect(
                window_handle,
                ctypes.byref(
                    native_rectangle,
                ),
            ):
                return True

            if (
                native_rectangle.right <= native_rectangle.left
                or native_rectangle.bottom <= native_rectangle.top
            ):
                return True

            snapshots.append(
                NativeWindowSnapshot(
                    handle=int(
                        window_handle,
                    ),
                    title=title,
                    rectangle=ScreenRectangle(
                        left=int(
                            native_rectangle.left,
                        ),
                        top=int(
                            native_rectangle.top,
                        ),
                        right=int(
                            native_rectangle.right,
                        ),
                        bottom=int(
                            native_rectangle.bottom,
                        ),
                    ),
                    is_visible=True,
                    is_minimized=bool(
                        is_iconic(
                            window_handle,
                        )
                    ),
                )
            )

            return True

        if not enum_windows(
            callback,
            0,
        ):
            error_code = ctypes.get_last_error()

            raise OSError(
                error_code,
                "EnumWindows no pudo enumerar las ventanas.",
            )

        return tuple(
            snapshots,
        )
