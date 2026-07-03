from __future__ import annotations

from pocket_option_analyzer.infrastructure.capture.models import Frame
from pocket_option_analyzer.infrastructure.capture.services.frame_buffer import FrameBuffer
from pocket_option_analyzer.infrastructure.capture.services.frame_factory import FrameFactory

from pocket_option_analyzer.infrastructure.windows.services.window_finder import WindowFinder
from pocket_option_analyzer.infrastructure.windows.services.window_reader import WindowReader

from pocket_option_analyzer.infrastructure.capture.contracts import ScreenCapture


class CaptureService:
    """
    Servicio responsable de capturar frames desde una ventana real.
    """

    def __init__(
        self,
        finder: WindowFinder,
        reader: WindowReader,
        capture: ScreenCapture,
        frame_factory: FrameFactory,
        frame_buffer: FrameBuffer,
    ) -> None:
        self._finder = finder
        self._reader = reader
        self._capture = capture
        self._frame_factory = frame_factory
        self._frame_buffer = frame_buffer

    def capture_once(self, title: str) -> Frame | None:
        """
        Captura un frame de la ventana cuyo título coincide.
        """

        window = self._finder.find(title)

        if window is None:
            return None

        window_info = self._reader.read(window.hwnd)

        image = self._capture.capture(window_info)

        frame = self._frame_factory.create(image)

        self._frame_buffer.append(frame)

        return frame

    def latest_frame(self) -> Frame | None:
        return self._frame_buffer.latest()

    def clear_buffer(self) -> None:
        self._frame_buffer.clear()