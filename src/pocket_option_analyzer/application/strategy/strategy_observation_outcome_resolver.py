from __future__ import annotations

from datetime import datetime

from pocket_option_analyzer.application.strategy.strategy_observation import (
    StrategyObservation,
)
from pocket_option_analyzer.application.strategy.strategy_observation_outcome import (
    StrategyObservationOutcome,
    StrategyObservationResolution,
    VisualPriceReference,
)
from pocket_option_analyzer.domain.signals import SignalDirection

from .current_visual_price_comparison_context import (
    CurrentVisualPriceComparisonContext,
)
from .visual_reference_validation import (
    VisualReferenceMovement,
    compare_visual_references,
)


class StrategyObservationOutcomeResolver:
    """Resolves passive observations on the first frame at or after expiry."""

    def __init__(self) -> None:
        self._pending: dict[str, StrategyObservation] = {}

    def add(self, observation: StrategyObservation) -> bool:
        if (
            observation.direction not in (SignalDirection.CALL, SignalDirection.PUT)
            or observation.entry_reference is None
        ):
            return False
        snapshot_id = observation.candle_interval_started_at.isoformat()
        if snapshot_id in self._pending:
            return False
        self._pending[snapshot_id] = observation
        return True

    def resolve_due(
        self,
        observed_at: datetime,
        exit_reference: VisualPriceReference | None,
        exit_visual_price_context: CurrentVisualPriceComparisonContext
        | None = None,
    ) -> tuple[StrategyObservationResolution, ...]:
        due = tuple(
            (snapshot_id, observation)
            for snapshot_id, observation in self._pending.items()
            if observed_at >= observation.resolve_at
        )
        resolutions = tuple(
            self._resolve(
                snapshot_id,
                observation,
                observed_at,
                exit_reference,
                exit_visual_price_context,
            )
            for snapshot_id, observation in due
        )
        for snapshot_id, _ in due:
            del self._pending[snapshot_id]
        return resolutions

    @staticmethod
    def _resolve(
        snapshot_id: str,
        observation: StrategyObservation,
        resolved_at: datetime,
        exit_reference: VisualPriceReference | None,
        exit_visual_price_context: CurrentVisualPriceComparisonContext | None,
    ) -> StrategyObservationResolution:
        entry_reference = observation.entry_reference
        direction = observation.direction
        assert entry_reference is not None
        assert direction in (SignalDirection.CALL, SignalDirection.PUT)
        outcome = StrategyObservationOutcomeResolver.compare(
            direction=direction,
            entry_reference=entry_reference,
            exit_reference=exit_reference,
        )
        return StrategyObservationResolution(
            snapshot_id=snapshot_id,
            observed_at=observation.observed_at,
            resolve_at=observation.resolve_at,
            resolved_at=resolved_at,
            direction=direction,
            entry_reference=entry_reference,
            exit_reference=exit_reference,
            outcome=outcome,
            entry_visual_price_context=getattr(
                observation,
                "visual_price_comparison_context",
                None,
            ),
            exit_visual_price_context=exit_visual_price_context,
        )

    @staticmethod
    def compare(
        direction: SignalDirection,
        entry_reference: VisualPriceReference | None,
        exit_reference: VisualPriceReference | None,
    ) -> StrategyObservationOutcome:
        movement = compare_visual_references(entry_reference, exit_reference)
        if movement is VisualReferenceMovement.UNRESOLVED:
            return StrategyObservationOutcome.UNRESOLVED
        if movement is VisualReferenceMovement.FLAT:
            return StrategyObservationOutcome.DRAW
        price_increased = movement is VisualReferenceMovement.UP
        if direction is SignalDirection.CALL:
            return (
                StrategyObservationOutcome.WIN
                if price_increased
                else StrategyObservationOutcome.LOSS
            )
        if direction is SignalDirection.PUT:
            return (
                StrategyObservationOutcome.LOSS
                if price_increased
                else StrategyObservationOutcome.WIN
            )
        return StrategyObservationOutcome.UNRESOLVED
