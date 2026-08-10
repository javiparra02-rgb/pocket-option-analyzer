from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np

from pocket_option_analyzer.vision.models import CurrentVisualPriceExtraction


@runtime_checkable
class CurrentVisualPriceExtractor(Protocol):
    """
    Contrato para extraer el precio visual actual desde una imagen.

    Las implementaciones concretas deciden cómo localizar el candidato y
    devuelven un resultado diagnosticable mediante el modelo canónico.
    """

    def extract(
        self,
        image: np.ndarray,
    ) -> CurrentVisualPriceExtraction:
        """
        Intenta localizar el precio visual actual en la imagen recibida.
        """

        ...
