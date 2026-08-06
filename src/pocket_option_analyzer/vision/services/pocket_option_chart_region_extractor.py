from __future__ import annotations

from math import isfinite
from numbers import Real

import numpy as np

from pocket_option_analyzer.vision.models import ChartRegion
from pocket_option_analyzer.vision.services.chart_region_image_validator import (
    require_valid_chart_region_image,
)


class PocketOptionChartRegionExtractor:
    """
    Extrae principalmente el área de velas de Pocket Option.

    Excluye proporcionalmente:
    - la barra superior del navegador y de Pocket Option;
    - el panel derecho de compra y venta;
    - el RSI, la línea temporal y otros paneles inferiores.

    Los indicadores se calculan internamente, por lo que no es
    necesario incluir los paneles RSI o Stochastic visibles.
    """

    def __init__(
        self,
        top_ratio: float = 0.10,
        right_ratio: float = 0.14,
        bottom_ratio: float = 0.15,
    ) -> None:
        self._top_ratio = self._resolve_ratio(
            name="top_ratio",
            value=top_ratio,
        )
        self._right_ratio = self._resolve_ratio(
            name="right_ratio",
            value=right_ratio,
        )
        self._bottom_ratio = self._resolve_ratio(
            name="bottom_ratio",
            value=bottom_ratio,
        )

        if self._top_ratio + self._bottom_ratio >= 1.0:
            raise ValueError("Top and bottom chart ratios must sum to less than one.")

    def extract(
        self,
        image: np.ndarray,
    ) -> ChartRegion:
        """
        Calcula proporcionalmente el área visual destinada a las velas.
        """

        validated_image = require_valid_chart_region_image(
            image,
        )

        image_height = int(
            validated_image.shape[0],
        )
        image_width = int(
            validated_image.shape[1],
        )

        x = 0
        y = int(
            image_height * self._top_ratio,
        )

        right_margin = int(
            image_width * self._right_ratio,
        )
        bottom_margin = int(
            image_height * self._bottom_ratio,
        )

        return ChartRegion(
            x=x,
            y=y,
            width=image_width - right_margin,
            height=image_height - y - bottom_margin,
        )

    @staticmethod
    def _resolve_ratio(
        *,
        name: str,
        value: float,
    ) -> float:
        """
        Normaliza y valida una proporción del extractor.
        """

        if isinstance(
            value,
            bool,
        ) or not isinstance(
            value,
            Real,
        ):
            raise TypeError(f"{name} must be a real number.")

        resolved_value = float(
            value,
        )

        if not isfinite(
            resolved_value,
        ):
            raise ValueError(f"{name} must be finite.")

        if not 0.0 <= resolved_value < 1.0:
            raise ValueError(f"{name} must be in range [0, 1).")

        return resolved_value
