from __future__ import annotations

from typing import Protocol

import numpy as np

from pocket_option_analyzer.infrastructure.capture.contracts.capture_region import (
    CaptureRegion,
)


class ScreenCapture(Protocol):
    """
    Contrato para capturar una región rectangular de la pantalla.
    """

    def capture(
        self,
        window: CaptureRegion,
    ) -> np.ndarray:
        """
        Captura la región especificada.

        Returns
        -------
        numpy.ndarray
            Imagen capturada.
        """

        ...
