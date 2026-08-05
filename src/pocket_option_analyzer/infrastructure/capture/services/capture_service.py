from __future__ import annotations

import numpy as np

from pocket_option_analyzer.infrastructure.capture.contracts import (
    ScreenCapture,
)
from pocket_option_analyzer.infrastructure.capture.errors import (
    CaptureUnavailableError,
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
from pocket_option_analyzer.vision.models import ChartRegion
from pocket_option_analyzer.vision.preprocessing import FrameValidator
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

    def capture_once(
        self,
    ) -> Frame | None:
        """
        Captura un único fotograma del gráfico.

        Devuelve None cuando la ventana no está disponible temporalmente.
        Los errores internos o inesperados continúan propagándose.
        """

        window = self._finder.find(
            self._window_title,
        )

        if window is None:
            return None

        try:
            window = self._reader.read(
                window.hwnd,
            )

            image = self._capture.capture(
                window,
            )
        except CaptureUnavailableError:
            return None

        if not self._is_capture_image_available(
            image,
        ):
            return None

        region = self._region_extractor.extract(
            image,
        )

        if not self._region_fits_image(
            region=region,
            image=image,
        ):
            return None

        roi = image[
            region.y : region.y + region.height,
            region.x : region.x + region.width,
        ].copy(
            order="C",
        )

        if not FrameValidator.validate(
            roi,
        ):
            return None

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

    @staticmethod
    def _is_capture_image_available(
        image: object,
    ) -> bool:
        """
        Valida el resultado entregado por el adaptador de captura.

        Una matriz vacía puede representar una indisponibilidad temporal.
        Un tipo o formato incompatible representa un error del contrato.
        """

        if not isinstance(
            image,
            np.ndarray,
        ):
            raise TypeError("Screen capture must return a NumPy array.")

        if image.size == 0:
            return False

        if not FrameValidator.validate(
            image,
        ):
            raise ValueError("Screen capture returned an unsupported image format.")

        return True

    @staticmethod
    def _region_fits_image(
        region: ChartRegion,
        image: np.ndarray,
    ) -> bool:
        """
        Comprueba que el ROI sea positivo y esté completamente contenido.

        La regla geométrica se mantiene en el modelo canónico ChartRegion.
        """

        return region.fits_within(
            image_width=int(
                image.shape[1],
            ),
            image_height=int(
                image.shape[0],
            ),
        )

    def latest_frame(self) -> Frame | None:
        return self._frame_buffer.latest()

    def clear_buffer(self) -> None:
        self._frame_buffer.clear()
