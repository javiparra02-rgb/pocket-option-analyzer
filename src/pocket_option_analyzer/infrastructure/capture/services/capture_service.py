from __future__ import annotations

from pocket_option_analyzer.infrastructure.capture.contracts import (
    ScreenCapture,
)
from pocket_option_analyzer.infrastructure.capture.models import Frame
from pocket_option_analyzer.infrastructure.capture.services.frame_buffer import (
    FrameBuffer,
)
from pocket_option_analyzer.infrastructure.capture.services.frame_factory import (
    FrameFactory,
)
from pocket_option_analyzer.infrastructure.windows.services import (
    WindowFinder,
    WindowReader,
)
from pocket_option_analyzer.vision.services import (
    ChartRegionExtractor,
    DatasetCaptureService,
)


class CaptureService:
    """
    Servicio principal encargado de capturar el gráfico.
    """

    def __init__(
        self,
        finder: WindowFinder,
        reader: WindowReader,
        capture: ScreenCapture,
        region_extractor: ChartRegionExtractor,
        frame_factory: FrameFactory,
        frame_buffer: FrameBuffer,
        dataset_capture: DatasetCaptureService | None = None,
        window_title: str = "Pocket Option",
    ) -> None:
        self._finder = finder
        self._reader = reader
        self._capture = capture
        self._region_extractor = region_extractor
        self._frame_factory = frame_factory
        self._frame_buffer = frame_buffer
        self._dataset_capture = dataset_capture
        self._window_title = window_title

    def capture_once(self) -> Frame | None:
        """
        Captura un único fotograma del gráfico.
        """

        window = self._finder.find(self._window_title)

        if window is None:
            return None

        window = self._reader.read(window.hwnd)

        image = self._capture.capture(
            window,
        )

        region = self._region_extractor.extract(
            image,
        )

        roi = image[
            region.y : region.y + region.height,
            region.x : region.x + region.width,
        ].copy(
            order="C",
        )

        if self._dataset_capture is not None:
            self._dataset_capture.save(
                roi,
            )

        frame = self._frame_factory.create(
            roi,
        )

        self._frame_buffer.append(
            frame,
        )

        return frame

    def latest_frame(self) -> Frame | None:
        return self._frame_buffer.latest()

    def clear_buffer(self) -> None:
        self._frame_buffer.clear()
