from __future__ import annotations

import numpy as np

from pocket_option_analyzer.vision.models.chart_region import ChartRegion


class ChartLocator:
    """
    Localizador del gráfico.

    Primera implementación basada en una región configurada.
    """

    def __init__(self, region: ChartRegion) -> None:
        self._region = region

    def locate(self, image: np.ndarray) -> ChartRegion:
        """
        Devuelve la región del gráfico.

        En futuras versiones analizará automáticamente la imagen.
        """
        return self._region
