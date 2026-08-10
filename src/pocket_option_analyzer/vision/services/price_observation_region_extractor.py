from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np

from pocket_option_analyzer.vision.models import ChartRegion


@runtime_checkable
class PriceObservationRegionExtractor(Protocol):
    """
    Contrato para localizar la región destinada a observar el precio.

    La región es independiente del ROI utilizado para analizar velas y
    utiliza el modelo rectangular canónico ChartRegion.
    """

    def extract(
        self,
        image: np.ndarray,
    ) -> ChartRegion:
        """
        Calcula la región visual donde debe observarse el precio.
        """

        ...
