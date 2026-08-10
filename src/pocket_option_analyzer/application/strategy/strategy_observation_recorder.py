from __future__ import annotations

from datetime import datetime
from typing import Protocol

from pocket_option_analyzer.application.strategy.strategy_observation import (
    StrategyObservation,
)
from pocket_option_analyzer.application.strategy.strategy_observation_outcome import (
    StrategyObservationResolution,
    VisualPriceReference,
)
from pocket_option_analyzer.application.strategy.strategy_observation_outcome_resolver import (  # noqa: E501
    StrategyObservationOutcomeResolver,
)
from pocket_option_analyzer.application.strategy.visual_reference_validation import (
    VisualReferenceResolution,
    VisualReferenceValidation,
)
from pocket_option_analyzer.application.strategy.visual_reference_validation_resolver import (  # noqa: E501
    VisualReferenceValidationResolver,
)


class StrategyObservationWriter(Protocol):
    def write(self, observation: StrategyObservation) -> None: ...

    def write_resolution(self, resolution: StrategyObservationResolution) -> None: ...

    def write_reference_validation(
        self,
        validation: VisualReferenceValidation,
    ) -> None: ...

    def write_reference_resolution(
        self,
        resolution: VisualReferenceResolution,
    ) -> None: ...


class StrategyObservationRecorder:
    """Persists at most one observation for each stable candle snapshot."""

    def __init__(
        self,
        writer: StrategyObservationWriter | None = None,
        resolver: StrategyObservationOutcomeResolver | None = None,
        reference_resolver: VisualReferenceValidationResolver | None = None,
    ) -> None:
        self._writer = writer
        self._resolver = resolver or StrategyObservationOutcomeResolver()
        self._reference_resolver = (
            reference_resolver or VisualReferenceValidationResolver()
        )
        self._seen_snapshot_ids: set[str] = set()

    def record(self, observation: StrategyObservation) -> bool:
        snapshot_id = observation.candle_interval_started_at.isoformat()
        if snapshot_id in self._seen_snapshot_ids:
            return False
        if self._writer is not None:
            self._writer.write(observation)
        self._seen_snapshot_ids.add(snapshot_id)
        self._resolver.add(observation)
        validation = self._reference_resolver.add(observation)
        if self._writer is not None and validation is not None:
            self._writer.write_reference_validation(validation)
        return True

    def resolve_due(
        self,
        observed_at: datetime,
        exit_reference: VisualPriceReference | None,
    ) -> tuple[StrategyObservationResolution, ...]:
        resolutions = self._resolver.resolve_due(observed_at, exit_reference)
        reference_resolutions = self._reference_resolver.resolve_due(
            observed_at,
            exit_reference,
        )
        if self._writer is not None:
            for resolution in resolutions:
                self._writer.write_resolution(resolution)
            for resolution in reference_resolutions:
                self._writer.write_reference_resolution(resolution)
        return resolutions
