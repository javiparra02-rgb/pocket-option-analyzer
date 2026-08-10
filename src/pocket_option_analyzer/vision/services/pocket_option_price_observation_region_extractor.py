from __future__ import annotations

from math import isfinite
from numbers import Real

import numpy as np

from pocket_option_analyzer.vision.models import ChartRegion
from pocket_option_analyzer.vision.services.chart_region_image_validator import (
    require_valid_chart_region_image,
)


class PocketOptionPriceObservationRegionExtractor:
    """
    Calcula una región independiente para observar el precio en Pocket Option.

    La geometría base coincide con el ROI proporcional de velas. La extensión
    inferior configurable ocupa parte de su margen inferior sin alterar el ROI
    de velas ni exceder los límites del frame.
    """

    def __init__(
        self,
        top_ratio: float = 0.10,
        right_ratio: float = 0.14,
        bottom_ratio: float = 0.15,
        bottom_extension_ratio: float = 0.0,
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
        self._bottom_extension_ratio = self._resolve_ratio(
            name="bottom_extension_ratio",
            value=bottom_extension_ratio,
        )

        if self._top_ratio + self._bottom_ratio >= 1.0:
            raise ValueError(
                "Top and bottom price observation ratios must sum to less than one."
            )

        if self._bottom_extension_ratio > self._bottom_ratio:
            raise ValueError(
                "Bottom extension ratio cannot exceed the bottom ratio."
            )

    def extract(
        self,
        image: np.ndarray,
    ) -> ChartRegion:
        """
        Calcula proporcionalmente la región destinada a observar el precio.
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
        bottom_extension = int(
            image_height * self._bottom_extension_ratio,
        )

        return ChartRegion(
            x=x,
            y=y,
            width=image_width - right_margin,
            height=image_height - y - bottom_margin + bottom_extension,
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
