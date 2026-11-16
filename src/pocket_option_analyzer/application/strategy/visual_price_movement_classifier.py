from __future__ import annotations

from math import isfinite
from numbers import Real

from .current_visual_price_comparison import (
    CurrentVisualPriceComparison,
    CurrentVisualPriceComparisonStatus,
)
from .price_movement import PriceMovement
from .visual_price_movement_classification import (
    VisualPriceMovementClassification,
    VisualPriceMovementClassificationDiagnostic,
)


class VisualPriceMovementClassifier:
    """Classifies canonical deltas for shadow telemetry only."""

    def __init__(self, pixel_tolerance: float | None = None) -> None:
        if pixel_tolerance is not None and (
            isinstance(pixel_tolerance, bool)
            or not isinstance(pixel_tolerance, Real)
            or not isfinite(pixel_tolerance)
            or pixel_tolerance < 0
        ):
            raise ValueError(
                "pixel_tolerance debe ser finito y mayor o igual que cero."
            )
        self._pixel_tolerance = (
            float(pixel_tolerance) if pixel_tolerance is not None else None
        )

    @property
    def pixel_tolerance(self) -> float | None:
        return self._pixel_tolerance

    def classify(
        self,
        comparison: CurrentVisualPriceComparison,
    ) -> VisualPriceMovementClassification:
        if (
            comparison.status is CurrentVisualPriceComparisonStatus.UNAVAILABLE
            and not comparison.has_accredited_comparison
        ):
            return VisualPriceMovementClassification(
                movement=PriceMovement.UNRESOLVED,
                epsilon=None,
                pixel_tolerance=self._pixel_tolerance,
                diagnostic=(
                    VisualPriceMovementClassificationDiagnostic.COMPARISON_UNAVAILABLE
                ),
            )

        if self._pixel_tolerance is None:
            return VisualPriceMovementClassification(
                movement=PriceMovement.UNRESOLVED,
                epsilon=None,
                pixel_tolerance=None,
                diagnostic=(
                    VisualPriceMovementClassificationDiagnostic.EPSILON_NOT_CALIBRATED
                ),
            )

        # A configured number is not a verified noise policy. I2 supplies no
        # production noise certifier; keep the constructor for old consumers,
        # but never classify diagnostic or TEST_ONLY geometry as real movement.
        diagnostic = (
            VisualPriceMovementClassificationDiagnostic.COMPARABILITY_NOT_VERIFIED
            if not comparison.has_accredited_comparison
            else VisualPriceMovementClassificationDiagnostic.NOISE_CALIBRATION_UNVERIFIED
        )
        return VisualPriceMovementClassification(
            movement=PriceMovement.UNRESOLVED,
            epsilon=None,
            pixel_tolerance=self._pixel_tolerance,
            diagnostic=diagnostic,
        )
