from __future__ import annotations

import numpy as np

from pocket_option_analyzer.vision.models import ChartRegion
from pocket_option_analyzer.vision.services.chart_region_image_validator import (
    require_valid_chart_region_image,
)


class FixedChartRegionExtractor:
    """
    Devuelve una región fija configurada para el gráfico.

    La región no se recorta ni modifica según el tamaño de la imagen.
    El consumidor decide posteriormente si cabe completamente dentro
    del frame actual.
    """

    def __init__(
        self,
        region: ChartRegion,
    ) -> None:
        if region.x < 0 or region.y < 0:
            raise ValueError("Fixed chart region coordinates cannot be negative.")

        if not region.has_positive_area:
            raise ValueError("Fixed chart region dimensions must be greater than zero.")

        self._region = region

    def extract(
        self,
        image: np.ndarray,
    ) -> ChartRegion:
        """
        Devuelve exactamente la región configurada.

        La imagen se valida para mantener el mismo contrato estructural
        que los demás extractores.
        """

        require_valid_chart_region_image(
            image,
        )

        return self._region
