import json
from datetime import UTC, datetime

from pocket_option_analyzer.application.strategy import (
    DirectionConditionAudit,
    StrategyCondition,
    StrategyConditionAudit,
    StrategyConditionResult,
    StrategyObservation,
)
from pocket_option_analyzer.domain.indicators import (
    EmaSnapshot,
    IndicatorSnapshot,
    RsiSnapshot,
    StochasticSnapshot,
)
from pocket_option_analyzer.domain.signals import SignalDirection
from pocket_option_analyzer.infrastructure.signals import (
    JsonlStrategyObservationWriter,
)
from pocket_option_analyzer.vision.models import TrendDirection


def _direction(direction: SignalDirection) -> DirectionConditionAudit:
    return DirectionConditionAudit(
        direction=direction,
        conditions=(
            StrategyConditionResult(StrategyCondition.TREND, True),
            StrategyConditionResult(
                StrategyCondition.RSI_RANGE, False, "RSI blocks",
            ),
        ),
    )


def test_writer_serializes_structured_audit_and_indicators(tmp_path) -> None:
    instant = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)
    observation = StrategyObservation(
        observed_at=instant,
        candle_interval_started_at=instant,
        audit=StrategyConditionAudit(
            call=_direction(SignalDirection.CALL),
            put=_direction(SignalDirection.PUT),
        ),
        trend=TrendDirection.BULLISH,
        indicators=IndicatorSnapshot(
            ema=EmaSnapshot(10.0, 9.0, 4),
            rsi=RsiSnapshot(60.0),
            stochastic=StochasticSnapshot(30.0, 20.0, 10.0, 15.0),
        ),
    )
    path = tmp_path / "observations.jsonl"

    JsonlStrategyObservationWriter(path).write(observation)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["snapshot_id"] == instant.isoformat()
    assert payload["call"]["passed_count"] == 1
    assert payload["call"]["conditions"]["rsi_range"]["passed"] is False
    assert payload["call"]["blockers"] == ["RSI blocks"]
    assert payload["indicators"]["stochastic"]["previous_d"] == 15.0
    assert "outcome" not in payload

