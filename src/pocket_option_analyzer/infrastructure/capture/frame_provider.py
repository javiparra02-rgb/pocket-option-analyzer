from __future__ import annotations

from datetime import datetime

from pocket_option_analyzer.infrastructure.capture.contracts import (
    ScreenCapture,
    WindowLocator,
)
from pocket_option_analyzer.infrastructure.capture.models import Frame


class PocketOptionFrameProvider:
    """
    Proveedor de fotogramas de la ventana de Pocket Option.
    """

    def __init__(
        self,
        locator: WindowLocator,
        capture: ScreenCapture,
        window_title: str = "Pocket Option",
    ) -> None:
        self._locator = locator
        self._capture = capture
        self._window_title = window_title
        self._frame_id = 0

    def get_frame(self) -> Frame | None:
        """
        Captura un fotograma de la ventana.

        Returns
        -------
        Frame | None
        """
        window = self._locator.find(self._window_title)

        if window is None:
            return None

        image = self._capture.capture(window)

        self._frame_id += 1

        return Frame(
            frame_id=self._frame_id,
            timestamp=datetime.now(),
            image=image,
        )