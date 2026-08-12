from __future__ import annotations

from datetime import UTC, datetime

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

    def __init__(self) -> None:
        self._next_frame_id = 1

    def create(
        self,
        image: np.ndarray,
        price_observation_image: np.ndarray | None = None,
        chart_region: ChartRegion | None = None,
        price_observation_region: ChartRegion | None = None,
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

        frame = Frame(
            frame_id=self._next_frame_id,
            timestamp=datetime.now(UTC),
            image=image,
            price_observation_image=price_observation_image,
            chart_region=chart_region,
            price_observation_region=price_observation_region,
        )

        self._next_frame_id += 1

        return frame
