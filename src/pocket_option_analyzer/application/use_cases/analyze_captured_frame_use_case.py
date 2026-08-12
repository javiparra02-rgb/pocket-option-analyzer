from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

import numpy as np

from pocket_option_analyzer.application.signals import (
    VisualSignalRecordingPipeline,
)
from pocket_option_analyzer.domain.signals import SignalRecord


@runtime_checkable
class FrameLike(Protocol):
    """
    Contrato mínimo que necesita el caso de uso.

    Así application no depende directamente de la implementación concreta
    del Frame en infrastructure.
    """

    image: np.ndarray


class AnalyzeCapturedFrameUseCase:
    """
    Caso de uso para analizar un frame capturado.

    Recibe un frame, extrae su imagen y delega el análisis al pipeline visual.

    No ejecuta operaciones.
    No hace clic.
    No interactúa con Pocket Option.
    Solo analiza el frame y registra la señal resultante.
    """

    def __init__(
        self,
        pipeline: VisualSignalRecordingPipeline,
        source: str = "captured_frame_visual_analysis",
    ) -> None:
        self._pipeline = pipeline
        self._source = source

    def execute(
        self,
        frame: FrameLike,
    ) -> SignalRecord:
        """
        Analiza el frame capturado y devuelve el registro de señal.
        """

        return self._pipeline.analyze_and_record(
            image=frame.image,
            price_observation_image=getattr(
                frame,
                "price_observation_image",
                None,
            ),
            chart_region=getattr(
                frame,
                "chart_region",
                None,
            ),
            price_observation_region=getattr(
                frame,
                "price_observation_region",
                None,
            ),
            created_at=self._resolve_created_at(frame),
            source=self._source,
        )

    def _resolve_created_at(
        self,
        frame: FrameLike,
    ) -> datetime | None:
        """
        Intenta reutilizar la fecha del frame si existe.

        Soporta nombres comunes:
        - captured_at
        - created_at
        - timestamp
        """

        for attribute_name in (
            "captured_at",
            "created_at",
            "timestamp",
        ):
            value = getattr(
                frame,
                attribute_name,
                None,
            )

            if isinstance(
                value,
                datetime,
            ):
                return value

        return None
