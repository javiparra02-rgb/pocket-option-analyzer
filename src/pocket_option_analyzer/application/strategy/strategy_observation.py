from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from pocket_option_analyzer.application.market import VisualIndicatorSnapshotContext
from pocket_option_analyzer.application.strategy.strategy_condition_audit import (
    StrategyConditionAudit,
)
from pocket_option_analyzer.domain.indicators import IndicatorSnapshot
from pocket_option_analyzer.domain.signals import SignalDirection
from pocket_option_analyzer.vision.models import (
    CandleFilterDiagnostics,
    CurrentVisualPriceExtraction,
    TrendDirection,
)

from .current_visual_price_comparison_context import (
    CurrentVisualPriceComparisonContext,
)
from .strategy_observation_outcome import (
    StrategyObservationOutcome,
    VisualPriceReference,
)
from .visual_price_reference_result import VisualPriceReferenceResult


@dataclass(frozen=True, slots=True)
class StrategyObservation:
    """Passive, structured evidence captured for one stable candle snapshot."""

    observed_at: datetime
    candle_interval_started_at: datetime
    audit: StrategyConditionAudit
    trend: TrendDirection
    indicators: IndicatorSnapshot
    resolve_at: datetime
    direction: SignalDirection | None
    entry_reference: VisualPriceReference | None
    entry_reference_result: VisualPriceReferenceResult | None = None
    current_visual_price: CurrentVisualPriceExtraction | None = None
    outcome: StrategyObservationOutcome = StrategyObservationOutcome.UNRESOLVED
    visual_context: VisualIndicatorSnapshotContext | None = None
    detection_diagnostics: CandleFilterDiagnostics | None = None
    visual_price_comparison_context: (
        CurrentVisualPriceComparisonContext | None
    ) = None

    def __post_init__(self) -> None:
        for field_name in (
            "observed_at",
            "resolve_at",
            "candle_interval_started_at",
        ):
            value = getattr(self, field_name)
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{field_name} debe incluir zona horaria.")
            object.__setattr__(self, field_name, value.astimezone(UTC))

        context = self.visual_price_comparison_context
        if context is None:
            return

        canonical_fields = (
            ("current_visual_price", context.current_visual_price),
            ("entry_reference_result", context.reference_result),
            ("entry_reference", context.reference_result.reference),
        )
        for field_name, canonical_value in canonical_fields:
            legacy_value = getattr(self, field_name)
            if legacy_value is not None and legacy_value != canonical_value:
                raise ValueError(
                    f"{field_name} debe coincidir con "
                    "visual_price_comparison_context."
                )
            object.__setattr__(self, field_name, canonical_value)

    @classmethod
    def resolve_time(cls, observed_at: datetime) -> datetime:
        return observed_at + timedelta(seconds=10)
