from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from pocket_option_analyzer.application.strategy import StrategyObservation
from pocket_option_analyzer.domain.signals import SignalDirection
from pocket_option_analyzer.vision.models import TrendDirection


def _observation(instant: datetime) -> StrategyObservation:
    return StrategyObservation(
        observed_at=instant,
        candle_interval_started_at=instant.replace(microsecond=0),
        audit=SimpleNamespace(),  # type: ignore[arg-type]
        trend=TrendDirection.SIDEWAYS,
        indicators=SimpleNamespace(),  # type: ignore[arg-type]
        resolve_at=instant + timedelta(seconds=10),
        direction=SignalDirection.CALL,
        entry_reference=None,
    )


def test_observation_normalizes_all_timestamps_to_utc() -> None:
    local_instant = datetime(
        2026,
        8,
        9,
        12,
        0,
        tzinfo=timezone(timedelta(hours=-4)),
    )

    observation = _observation(local_instant)

    assert observation.observed_at == datetime(2026, 8, 9, 16, 0, tzinfo=UTC)
    assert observation.resolve_at == datetime(2026, 8, 9, 16, 0, 10, tzinfo=UTC)
    assert observation.candle_interval_started_at.tzinfo is UTC


def test_observation_rejects_timezone_naive_timestamps() -> None:
    with pytest.raises(ValueError, match="zona horaria"):
        _observation(datetime(2026, 8, 9, 12, 0))
