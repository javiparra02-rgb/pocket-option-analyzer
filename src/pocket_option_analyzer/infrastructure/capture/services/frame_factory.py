from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from time import monotonic_ns

import numpy as np

from pocket_option_analyzer.infrastructure.capture.models import Frame
from pocket_option_analyzer.vision.models import ChartRegion


class FrameFactory:
    """
    Crea frames con identificadores incrementales locales al proceso.

    La fábrica conserva únicamente el siguiente identificador. No
    mantiene referencias a los frames creados ni reinicia la secuencia
    durante la ejecución.
    """

    def __init__(
        self,
        *,
        wall_clock: Callable[[], datetime] | None = None,
        monotonic_clock_ns: Callable[[], int] | None = None,
    ) -> None:
        self._next_frame_id = 1
        self._wall_clock = wall_clock or (lambda: datetime.now(UTC))
        self._monotonic_clock_ns = monotonic_clock_ns or monotonic_ns

    def create(
        self,
        image: np.ndarray,
        price_observation_image: np.ndarray | None = None,
        chart_region: ChartRegion | None = None,
        price_observation_region: ChartRegion | None = None,
        source_key: str | None = None,
    ) -> Frame:
        """
        Crea un nuevo Frame.

        Parameters
        ----------
        image:
            Imagen capturada.
        price_observation_image:
            Imagen opcional para observar el precio visual.

        Returns
        -------
        Frame
        """

        captured_at = self._wall_clock()
        monotonic_timestamp_ns = self._monotonic_clock_ns()
        if captured_at.tzinfo is None or captured_at.utcoffset() is None:
            raise ValueError("Frame wall clock must return an aware datetime.")
        if monotonic_timestamp_ns < 0:
            raise ValueError("Frame monotonic timestamp cannot be negative.")
        if source_key is not None and not source_key:
            raise ValueError("Frame source_key cannot be empty.")

        frame = Frame(
            frame_id=self._next_frame_id,
            timestamp=captured_at,
            image=image,
            price_observation_image=price_observation_image,
            chart_region=chart_region,
            price_observation_region=price_observation_region,
            monotonic_timestamp_ns=monotonic_timestamp_ns,
            source_key=source_key,
        )

        self._next_frame_id += 1

        return frame
