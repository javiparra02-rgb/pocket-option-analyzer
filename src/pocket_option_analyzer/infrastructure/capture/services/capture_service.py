from __future__ import annotations

from datetime import UTC, datetime
from time import monotonic_ns
from typing import Any

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
    PriceObservationRegionExtractor,
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
        price_observation_region_extractor: PriceObservationRegionExtractor
        | None = None,
        observational_evidence_enabled: bool = False,
        instrument_context_region: ChartRegion | None = None,
        observational_frame_byte_limit: int | None = None,
    ) -> None:
        self._finder = finder
        self._reader = reader
        self._capture = capture
        self._region_extractor = region_extractor
        self._frame_factory = frame_factory
        self._frame_buffer = frame_buffer
        self._dataset_capture = dataset_capture
        self._window_title = window_title
        self._price_observation_region_extractor = (
            price_observation_region_extractor
        )
        self._observational_evidence_enabled = observational_evidence_enabled
        self._instrument_context_region = instrument_context_region
        self._observational_frame_byte_limit = observational_frame_byte_limit

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

            capture_metadata: dict[str, Any] | None = None
            if self._observational_evidence_enabled:
                capture_metadata = {
                    "call_started_at": datetime.now(UTC).isoformat(),
                    "call_started_monotonic_ns": monotonic_ns(),
                }
            image = self._capture.capture(
                window,
            )
            if capture_metadata is not None:
                capture_metadata.update(
                    {
                        "call_finished_monotonic_ns": monotonic_ns(),
                        "call_finished_at": datetime.now(UTC).isoformat(),
                        "quote_effective_at": None,
                        "semantics": "LOCAL_CAPTURE_CALL_BRACKET_NOT_QUOTE_TIME",
                    }
                )
                capture_metadata["wall_clock_regressed"] = (
                    capture_metadata["call_finished_at"]
                    < capture_metadata["call_started_at"]
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

        price_observation_image: np.ndarray | None = None
        price_observation_region: ChartRegion | None = None

        if self._price_observation_region_extractor is not None:
            price_observation_region = (
                self._price_observation_region_extractor.extract(
                    image,
                )
            )

            if not self._region_fits_image(
                region=price_observation_region,
                image=image,
            ):
                return None

            price_observation_image = image[
                price_observation_region.y : (
                    price_observation_region.y
                    + price_observation_region.height
                ),
                price_observation_region.x : (
                    price_observation_region.x
                    + price_observation_region.width
                ),
            ].copy(
                order="C",
            )

            if not FrameValidator.validate(
                price_observation_image,
            ):
                return None

        if self._dataset_capture is not None:
            self._dataset_capture.save(
                roi,
            )

        experimental: dict[str, Any] = {}
        if self._observational_evidence_enabled:
            context_region = self._instrument_context_region
            context_image = None
            context_fits = context_region is not None and self._region_fits_image(
                context_region, image
            )
            context_bytes = (
                context_region.width
                * context_region.height
                * image.shape[2]
                * image.itemsize
                if context_region is not None
                else 0
            )
            context_budget = (
                self._observational_frame_byte_limit is not None
                and roi.nbytes
                + (
                    price_observation_image.nbytes
                    if price_observation_image is not None
                    else 0
                )
                + context_bytes
                <= self._observational_frame_byte_limit
            )
            if context_region is not None and context_fits and context_budget:
                # Same acquisition, not a new screenshot or an inferred asset.
                context_image = image[
                    context_region.y : context_region.y + context_region.height,
                    context_region.x : context_region.x + context_region.width,
                ].copy(order="C")
            if capture_metadata is not None:
                capture_metadata["context_byte_budget_satisfied"] = context_budget
                capture_metadata["instrument_identity"] = "UNKNOWN"
                capture_metadata["context_region"] = (
                    {
                        "x": context_region.x,
                        "y": context_region.y,
                        "width": context_region.width,
                        "height": context_region.height,
                    }
                    if context_region is not None and context_image is not None
                    else None
                )
            experimental = {
                "instrument_context_image": context_image,
                "capture_metadata": capture_metadata,
            }
        frame = self._frame_factory.create(
            image=roi,
            price_observation_image=price_observation_image,
            chart_region=region,
            price_observation_region=price_observation_region,
            source_key=f"win32_hwnd:{window.hwnd}",
            **experimental,
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
