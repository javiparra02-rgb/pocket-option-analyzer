from __future__ import annotations

from datetime import datetime

import numpy as np

from pocket_option_analyzer.infrastructure.capture.models import Frame


class FrameFactory:
    """
    Crea frames con identificadores incrementales locales al proceso.

    La fábrica conserva únicamente el siguiente identificador. No
    mantiene referencias a los frames creados ni reinicia la secuencia
    durante la ejecución.
    """

    def __init__(self) -> None:
        self._next_frame_id = 1

    def create(self, image: np.ndarray) -> Frame:
        """
        Crea un nuevo Frame.

        Parameters
        ----------
        image:
            Imagen capturada.

        Returns
        -------
        Frame
        """

        frame = Frame(
            frame_id=self._next_frame_id,
            timestamp=datetime.now(),
            image=image,
        )

        self._next_frame_id += 1

        return frame
