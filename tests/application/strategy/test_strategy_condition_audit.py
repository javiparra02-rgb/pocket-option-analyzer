import pytest

from pocket_option_analyzer.application.strategy import (
    DirectionConditionAudit,
    StrategyCondition,
    StrategyConditionResult,
)
from pocket_option_analyzer.domain.signals import SignalDirection


def test_condition_result_requires_reason_only_when_failed() -> None:
    with pytest.raises(ValueError, match="passed condition"):
        StrategyConditionResult(
            condition=StrategyCondition.TREND,
            passed=True,
            failure_reason="unexpected",
        )

    with pytest.raises(ValueError, match="failed condition"):
        StrategyConditionResult(
            condition=StrategyCondition.TREND,
            passed=False,
        )


def test_direction_audit_reports_counts_and_failures() -> None:
    audit = DirectionConditionAudit(
        direction=SignalDirection.CALL,
        conditions=(
            StrategyConditionResult(
                condition=StrategyCondition.TREND,
                passed=True,
            ),
            StrategyConditionResult(
                condition=StrategyCondition.RSI_RANGE,
                passed=False,
                failure_reason="RSI is not in CALL range",
            ),
        ),
    )

    assert audit.passed_count == 1
    assert audit.total_count == 2
    assert audit.is_confirmed is False
    assert audit.failures == ("RSI is not in CALL range",)


def test_direction_audit_rejects_none_direction() -> None:
    with pytest.raises(ValueError, match="CALL or PUT"):
        DirectionConditionAudit(
            direction=SignalDirection.NONE,
            conditions=(),
        )
