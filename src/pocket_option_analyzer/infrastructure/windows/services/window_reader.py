from __future__ import annotations

from pocket_option_analyzer.infrastructure.capture.errors import (
    CaptureUnavailableError,
)
from pocket_option_analyzer.infrastructure.windows.models import (
    Win32WindowInfo,
)
from pocket_option_analyzer.infrastructure.windows.native import (
    POINT,
    User32,
)
from pocket_option_analyzer.infrastructure.windows.services.window_factory import (
    WindowFactory,
)


class WindowReader:
    """
    Construye un Win32WindowInfo completo a partir de un HWND.

    Los cambios externos de estado de una ventana se traducen a
    CaptureUnavailableError para que el ciclo de captura pueda
    recuperarse sin ocultar errores internos inesperados.
    """

    def __init__(
        self,
        user32: User32,
        factory: WindowFactory,
    ) -> None:
        self._user32 = user32
        self._factory = factory

    def read(
        self,
        hwnd: int,
    ) -> Win32WindowInfo:
        """
        Lee y valida la información actual de una ventana Win32.
        """

        if hwnd <= 0:
            raise ValueError("Window handle must be greater than zero.")

        if not self._user32.is_window(
            hwnd,
        ):
            raise CaptureUnavailableError(f"Window no longer exists: hwnd={hwnd}.")

        visible = self._user32.is_window_visible(
            hwnd,
        )

        minimized = self._user32.is_iconic(
            hwnd,
        )

        if not visible or minimized:
            raise CaptureUnavailableError(
                f"Window is not available for capture: hwnd={hwnd}."
            )

        try:
            title = self._user32.get_window_text(
                hwnd,
            ).strip()

            if not title:
                raise CaptureUnavailableError(f"Window title is empty for hwnd={hwnd}.")

            window_rect = self._user32.get_window_rect(
                hwnd,
            )

            client_rect = self._user32.get_client_rect(
                hwnd,
            )

            client_origin = self._user32.client_to_screen(
                hwnd,
                POINT(
                    0,
                    0,
                ),
            )
        except OSError as error:
            raise CaptureUnavailableError(
                f"Could not read Win32 window information: hwnd={hwnd}."
            ) from error

        width = window_rect.right - window_rect.left
        height = window_rect.bottom - window_rect.top

        if width <= 0 or height <= 0:
            raise CaptureUnavailableError(
                f"Window has invalid capture geometry: hwnd={hwnd}."
            )

        client_width = client_rect.right - client_rect.left
        client_height = client_rect.bottom - client_rect.top

        return self._factory.create(
            hwnd=hwnd,
            title=title,
            left=window_rect.left,
            top=window_rect.top,
            width=width,
            height=height,
            client_left=client_origin.x,
            client_top=client_origin.y,
            client_width=client_width,
            client_height=client_height,
            visible=visible,
            minimized=minimized,
        )
