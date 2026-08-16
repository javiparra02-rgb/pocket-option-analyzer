from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from numbers import Real

from .price_movement import PriceMovement


class VisualPriceMovementClassificationDiagnostic(StrEnum):
    CLASSIFIED = "classified"
    COMPARISON_UNAVAILABLE = "comparison_unavailable"
    EPSILON_NOT_CALIBRATED = "epsilon_not_calibrated"


@dataclass(frozen=True, slots=True)
class VisualPriceMovementClassification:
    """Shadow-only classification derived from canonical visual evidence."""

    movement: PriceMovement
    epsilon: float | None
    pixel_tolerance: float | None
    diagnostic: VisualPriceMovementClassificationDiagnostic

    def __post_init__(self) -> None:
        if not isinstance(self.movement, PriceMovement):
            raise ValueError("movement debe ser PriceMovement.")
        if not isinstance(
            self.diagnostic,
            VisualPriceMovementClassificationDiagnostic,
        ):
            raise ValueError(
                "diagnostic debe ser VisualPriceMovementClassificationDiagnostic."
            )
        for field_name, value in (
            ("epsilon", self.epsilon),
            ("pixel_tolerance", self.pixel_tolerance),
        ):
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, Real)
                or not isfinite(value)
                or value < 0
            ):
                raise ValueError(
                    f"{field_name} debe ser finito y mayor o igual que cero."
                )

        if self.diagnostic is VisualPriceMovementClassificationDiagnostic.CLASSIFIED:
            if self.movement is PriceMovement.UNRESOLVED:
                raise ValueError("CLASSIFIED requiere un movimiento resuelto.")
            if self.epsilon is None or self.pixel_tolerance is None:
                raise ValueError(
                    "CLASSIFIED requiere epsilon y pixel_tolerance."
                )
            return

        if self.movement is not PriceMovement.UNRESOLVED:
            raise ValueError(
                "Una clasificación no disponible debe ser UNRESOLVED."
            )
        if self.epsilon is not None:
            raise ValueError(
                "Una clasificación no disponible requiere epsilon=None."
            )
        if (
            self.diagnostic
            is VisualPriceMovementClassificationDiagnostic.EPSILON_NOT_CALIBRATED
            and self.pixel_tolerance is not None
        ):
            raise ValueError(
                "EPSILON_NOT_CALIBRATED requiere pixel_tolerance=None."
            )
