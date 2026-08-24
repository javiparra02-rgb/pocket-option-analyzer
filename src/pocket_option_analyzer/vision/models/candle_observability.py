from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .candle_type import CandleType


class CandleCloseBoundary(StrEnum):
    """Body boundary that represents the close for a directional candle."""

    BODY_TOP = "body_top"
    BODY_BOTTOM = "body_bottom"


@dataclass(frozen=True, slots=True)
class CandleObservability:
    """Immutable ROI-boundary facts derived from an observed candle body."""

    roi_height: int
    body_top_y: int
    body_bottom_y: int
    body_touches_top: bool
    body_touches_bottom: bool

    def __post_init__(self) -> None:
        if self.roi_height < 1:
            raise ValueError("roi_height debe ser positivo.")
        if not 0 <= self.body_top_y <= self.body_bottom_y < self.roi_height:
            raise ValueError("La geometría corporal debe pertenecer al ROI.")
        if self.body_touches_top != (self.body_top_y == 0):
            raise ValueError("body_touches_top debe coincidir con body_top_y.")
        if self.body_touches_bottom != (
            self.body_bottom_y == self.roi_height - 1
        ):
            raise ValueError(
                "body_touches_bottom debe coincidir con body_bottom_y."
            )

    def close_boundary_for(
        self,
        candle_type: CandleType,
    ) -> CandleCloseBoundary | None:
        """Return the body boundary that defines a directional close."""

        if candle_type is CandleType.BULLISH:
            return CandleCloseBoundary.BODY_TOP
        if candle_type is CandleType.BEARISH:
            return CandleCloseBoundary.BODY_BOTTOM
        return None

    def fully_observable_close_for(
        self,
        candle_type: CandleType,
    ) -> bool | None:
        """Report whether the close-defining body edge is inside the ROI."""

        boundary = self.close_boundary_for(candle_type)
        if boundary is CandleCloseBoundary.BODY_TOP:
            return not self.body_touches_top
        if boundary is CandleCloseBoundary.BODY_BOTTOM:
            return not self.body_touches_bottom
        return None
