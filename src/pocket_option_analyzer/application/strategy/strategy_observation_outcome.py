from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from pocket_option_analyzer.domain.signals import SignalDirection
from pocket_option_analyzer.vision.models import CurrentVisualPriceExtraction


class StrategyObservationOutcome(StrEnum):
    WIN = "win"
    LOSS = "loss"
    DRAW = "draw"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class VisualPriceReference:
    """ROI-local close normalized against stable closed-candle anchors."""

    value: float
    anchor_shape: tuple[tuple[str, float, float, float, float], ...] = ()
    source: str = "roi_local_close_normalized_by_closed_candle_range"

    @property
    def normalized_close(self) -> float:
        return self.value


@dataclass(frozen=True, slots=True)
class StrategyObservationResolution:
    snapshot_id: str
    observed_at: datetime
    resolve_at: datetime
    resolved_at: datetime
    direction: SignalDirection
    entry_reference: VisualPriceReference
    exit_reference: VisualPriceReference | None
    outcome: StrategyObservationOutcome
    exit_current_visual_price: CurrentVisualPriceExtraction | None = None
    entry_visual_price_context: (
        comparison_context.CurrentVisualPriceComparisonContext | None
    ) = None
    exit_visual_price_context: (
        comparison_context.CurrentVisualPriceComparisonContext | None
    ) = None

    def __post_init__(self) -> None:
        for field_name in ("observed_at", "resolve_at", "resolved_at"):
            value = getattr(self, field_name)
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{field_name} debe incluir zona horaria.")
            object.__setattr__(self, field_name, value.astimezone(UTC))


# Imported after VisualPriceReference is defined to break the existing cycle:
# context -> reference result -> this module -> context.
from . import (  # noqa: E402, I001
    current_visual_price_comparison_context as comparison_context,
)
