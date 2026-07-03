from __future__ import annotations

from abc import ABC
from abc import abstractmethod

import numpy as np

from pocket_option_analyzer.infrastructure.capture.models import WindowInfo


class CaptureApi(ABC):
    """
    Contrato para cualquier tecnología de captura.
    """

    @abstractmethod
    def capture(
        self,
        window: WindowInfo,
    ) -> np.ndarray:
        """
        Captura una ventana.
        """