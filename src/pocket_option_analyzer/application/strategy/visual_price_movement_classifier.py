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
        if comparison.status is CurrentVisualPriceComparisonStatus.UNAVAILABLE:
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

        delta = comparison.delta
        entry_span = comparison.entry_anchor_span_px
        exit_span = comparison.exit_anchor_span_px
        assert delta is not None
        assert entry_span is not None
        assert exit_span is not None
        epsilon = (
            self._pixel_tolerance / entry_span
            + self._pixel_tolerance / exit_span
        )
        if abs(delta) <= epsilon:
            movement = PriceMovement.FLAT
        elif delta > epsilon:
            movement = PriceMovement.UP
        else:
            movement = PriceMovement.DOWN

        return VisualPriceMovementClassification(
            movement=movement,
            epsilon=epsilon,
            pixel_tolerance=self._pixel_tolerance,
            diagnostic=VisualPriceMovementClassificationDiagnostic.CLASSIFIED,
        )
