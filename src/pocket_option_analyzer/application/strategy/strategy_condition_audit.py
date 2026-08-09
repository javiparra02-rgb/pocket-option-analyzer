from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pocket_option_analyzer.domain.signals import SignalDirection


class StrategyCondition(StrEnum):
    """Stable identifiers for the seven STRICT strategy requirements."""

    TREND = "trend"
    EMA_ALIGNMENT = "ema_alignment"
    EMA_SEPARATION = "ema_separation"
    RSI_RANGE = "rsi_range"
    STOCHASTIC_CROSS = "stochastic_cross"
    STOCHASTIC_TRIGGER_ZONE = "stochastic_trigger_zone"
    RECENT_CANDLE_CONFIRMATION = "recent_candle_confirmation"


@dataclass(frozen=True, slots=True)
class StrategyConditionResult:
    """Outcome of one condition for one candidate direction."""

    condition: StrategyCondition
    passed: bool
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        if self.passed and self.failure_reason is not None:
            raise ValueError("a passed condition cannot have a failure reason")
        if not self.passed and not self.failure_reason:
            raise ValueError("a failed condition must have a failure reason")


@dataclass(frozen=True, slots=True)
class DirectionConditionAudit:
    """Structured STRICT evaluation for a CALL or PUT candidate."""

    direction: SignalDirection
    conditions: tuple[StrategyConditionResult, ...]

    def __post_init__(self) -> None:
        if self.direction not in {SignalDirection.CALL, SignalDirection.PUT}:
            raise ValueError("audit direction must be CALL or PUT")

    @property
    def passed_count(self) -> int:
        return sum(result.passed for result in self.conditions)

    @property
    def total_count(self) -> int:
        return len(self.conditions)

    @property
    def is_confirmed(self) -> bool:
        return self.passed_count == self.total_count

    @property
    def failures(self) -> tuple[str, ...]:
        return tuple(
            result.failure_reason
            for result in self.conditions
            if result.failure_reason is not None
        )


@dataclass(frozen=True, slots=True)
class StrategyConditionAudit:
    """Structured CALL and PUT condition outcomes for one evaluation."""

    call: DirectionConditionAudit
    put: DirectionConditionAudit
