from __future__ import annotations

from typing import Protocol

from pocket_option_analyzer.application.strategy.strategy_observation import (
    StrategyObservation,
)


class StrategyObservationWriter(Protocol):
    def write(self, observation: StrategyObservation) -> None: ...


class StrategyObservationRecorder:
    """Persists at most one observation for each stable candle snapshot."""

    def __init__(self, writer: StrategyObservationWriter | None = None) -> None:
        self._writer = writer
        self._seen_snapshot_ids: set[str] = set()

    def record(self, observation: StrategyObservation) -> bool:
        snapshot_id = observation.candle_interval_started_at.isoformat()
        if snapshot_id in self._seen_snapshot_ids:
            return False
        if self._writer is not None:
            self._writer.write(observation)
        self._seen_snapshot_ids.add(snapshot_id)
        return True

