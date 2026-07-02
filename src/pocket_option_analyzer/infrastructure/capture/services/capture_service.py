from __future__ import annotations

from pocket_option_analyzer.infrastructure.capture.contracts import (
    ScreenCapture,
    WindowLocator,
)
from pocket_option_analyzer.infrastructure.capture.models import Frame
from pocket_option_analyzer.infrastructure.capture.services.frame_buffer import (
    FrameBuffer,
)
from pocket_option_analyzer.infrastructure.capture.services.frame_factory import (
    FrameFactory,
)


class CaptureService:
    """
    Servicio responsable de capturar fotogramas desde una ventana.
    """

    def __init__(
        self,
        locator: WindowLocator,
        capture: ScreenCapture,
        frame_factory: FrameFactory,
        frame_buffer: FrameBuffer,
        window_title: str = "Pocket Option",
    ) -> None:
        self._locator = locator
        self._capture = capture
        self._frame_factory = frame_factory
        self._frame_buffer = frame_buffer
        self._window_title = window_title

    def capture_once(self) -> Frame | None:
        """
        Captura un único fotograma.
        """
        window = self._locator.find(self._window_title)

        if window is None:
            return None

        image = self._capture.capture(window)

        frame = self._frame_factory.create(image)

        self._frame_buffer.append(frame)

        return frame

    def latest_frame(self) -> Frame | None:
        """
        Devuelve el último fotograma capturado.
        """
        return self._frame_buffer.latest()

    def clear_buffer(self) -> None:
        """
        Vacía el búfer.
        """
        self._frame_buffer.clear()