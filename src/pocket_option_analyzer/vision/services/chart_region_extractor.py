from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np

from pocket_option_analyzer.vision.models import ChartRegion


@runtime_checkable
class ChartRegionExtractor(Protocol):
    """
    Contrato para localizar el gráfico dentro de una imagen capturada.

    Las implementaciones deben devolver coordenadas relativas a la
    imagen recibida, utilizando el modelo canónico ChartRegion.
    """

    def extract(
        self,
        image: np.ndarray,
    ) -> ChartRegion:
        """
        Calcula la región visual que debe analizarse.
        """

        ...
