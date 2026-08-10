from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pocket_option_analyzer.application.market import VisualIndicatorSnapshotContext
from pocket_option_analyzer.application.strategy.strategy_condition_audit import (
    StrategyConditionAudit,
)
from pocket_option_analyzer.domain.indicators import IndicatorSnapshot
from pocket_option_analyzer.vision.models import CandleFilterDiagnostics, TrendDirection


@dataclass(frozen=True, slots=True)
class StrategyObservation:
    """Passive, structured evidence captured for one stable candle snapshot."""

    observed_at: datetime
    candle_interval_started_at: datetime
    audit: StrategyConditionAudit
    trend: TrendDirection
    indicators: IndicatorSnapshot
    visual_context: VisualIndicatorSnapshotContext | None = None
    detection_diagnostics: CandleFilterDiagnostics | None = None

