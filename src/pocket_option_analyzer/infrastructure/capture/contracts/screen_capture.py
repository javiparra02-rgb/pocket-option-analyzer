from __future__ import annotations

from typing import Protocol

import numpy as np

from pocket_option_analyzer.infrastructure.capture.models import WindowInfo


class ScreenCapture(Protocol):
    """
    Contrato para la captura de una región de pantalla.
    """

    def capture(self, window: WindowInfo) -> np.ndarray:
        """
        Captura la región especificada.

        Returns
        -------
        numpy.ndarray
            Imagen capturada.
        """
        ...
