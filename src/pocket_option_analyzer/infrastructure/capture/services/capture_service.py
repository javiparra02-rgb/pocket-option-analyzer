from __future__ import annotations

from pocket_option_analyzer.infrastructure.capture.models import Frame
from pocket_option_analyzer.infrastructure.capture.services.frame_buffer import FrameBuffer
from pocket_option_analyzer.infrastructure.capture.services.frame_factory import FrameFactory

from pocket_option_analyzer.infrastructure.windows.services.window_finder import WindowFinder
from pocket_option_analyzer.infrastructure.windows.services.window_reader import WindowReader

from pocket_option_analyzer.vision.services.chart_region_extractor import ChartRegionExtractor

from pocket_option_analyzer.infrastructure.capture.contracts import ScreenCapture


class CaptureService:
    """
    Servicio responsable de capturar SOLO el área del gráfico.
    """

    def __init__(
        self,
        finder: WindowFinder,
        reader: WindowReader,
        region_extractor: ChartRegionExtractor,
        capture: ScreenCapture,
        frame_factory: FrameFactory,
        frame_buffer: FrameBuffer,
    ) -> None:
        self._finder = finder
        self._reader = reader
        self._region_extractor = region_extractor
        self._capture = capture
        self._frame_factory = frame_factory
        self._frame_buffer = frame_buffer

    def capture_once(self, title: str) -> Frame | None:
        """
        Captura SOLO el chart ROI.
        """

        window = self._finder.find(title)

        if window is None:
            return None

        window_info = self._reader.read(window.hwnd)

        region = self._region_extractor.extract(window_info)

        image = self._capture.capture(region)

        frame = self._frame_factory.create(image)

        self._frame_buffer.append(frame)

        return frame

    def latest_frame(self) -> Frame | None:
        return self._frame_buffer.latest()

    def clear_buffer(self) -> None:
        self._frame_buffer.clear()