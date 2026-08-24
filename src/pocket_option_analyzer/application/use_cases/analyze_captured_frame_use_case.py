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
        self._session_key: str | None = None

    def start_session(self, *, session_key: str) -> None:
        """Start a fresh continuous-analysis session."""

        if not session_key:
            raise ValueError("session_key cannot be empty.")
        self._pipeline.start_session(session_key=session_key)
        self._session_key = session_key

    def stop_session(self) -> None:
        """Stop and clear all session-scoped analysis state."""

        try:
            self._pipeline.stop_session()
        finally:
            self._session_key = None

    def execute(
        self,
        frame: FrameLike,
    ) -> SignalRecord:
        """
        Analiza el frame capturado y devuelve el registro de señal.
        """

        created_at = self._resolve_created_at(frame)
        frame_id = getattr(frame, "frame_id", None)
        monotonic_timestamp = self._resolve_monotonic_timestamp(frame)
        source_key = self._resolve_source_key(frame)
        identity_session_key = (
            self._session_key
            if (
                frame_id is not None
                and created_at is not None
                and monotonic_timestamp is not None
                and source_key is not None
            )
            else None
        )
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
            created_at=created_at,
            source=self._source,
            frame_id=frame_id,
            monotonic_timestamp=monotonic_timestamp,
            source_key=source_key,
            session_key=identity_session_key,
        )

    @staticmethod
    def _resolve_monotonic_timestamp(frame: FrameLike) -> float | None:
        timestamp_ns = getattr(frame, "monotonic_timestamp_ns", None)
        if timestamp_ns is None:
            return None
        if not isinstance(timestamp_ns, int) or timestamp_ns < 0:
            raise ValueError(
                "Frame monotonic_timestamp_ns must be a non-negative integer."
            )
        return timestamp_ns / 1_000_000_000

    @staticmethod
    def _resolve_source_key(frame: FrameLike) -> str | None:
        source_key = getattr(frame, "source_key", None)
        if source_key is None:
            return None
        if not isinstance(source_key, str) or not source_key:
            raise ValueError("Frame source_key must be a non-empty string.")
        return source_key

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
