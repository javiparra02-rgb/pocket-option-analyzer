from __future__ import annotations

from datetime import datetime

from .current_visual_price_comparison_context import (
    CurrentVisualPriceComparisonContext,
)
from .strategy_observation import StrategyObservation
from .strategy_observation_outcome import VisualPriceReference
from .visual_reference_validation import (
    VisualReferenceResolution,
    VisualReferenceValidation,
    compare_visual_references,
    unresolved_diagnostic,
)


class VisualReferenceValidationResolver:
    """Resolves every deduplicated snapshot on its first due frame."""

    def __init__(self) -> None:
        self._pending: dict[str, VisualReferenceValidation] = {}

    def add(self, observation: StrategyObservation) -> VisualReferenceValidation | None:
        snapshot_id = observation.candle_interval_started_at.isoformat()
        if snapshot_id in self._pending:
            return None
        validation = VisualReferenceValidation(
            snapshot_id=snapshot_id,
            observed_at=observation.observed_at,
            resolve_at=observation.resolve_at,
            entry_reference=observation.entry_reference,
            entry_reference_result=observation.entry_reference_result,
            current_visual_price=observation.current_visual_price,
            entry_visual_price_context=getattr(
                observation,
                "visual_price_comparison_context",
                None,
            ),
        )
        self._pending[snapshot_id] = validation
        return validation

    def resolve_due(
        self,
        observed_at: datetime,
        exit_reference: VisualPriceReference | None,
        exit_visual_price_context: CurrentVisualPriceComparisonContext
        | None = None,
    ) -> tuple[VisualReferenceResolution, ...]:
        due = tuple(
            validation
            for validation in self._pending.values()
            if observed_at >= validation.resolve_at
        )
        resolutions = tuple(
            VisualReferenceResolution(
                snapshot_id=validation.snapshot_id,
                observed_at=validation.observed_at,
                resolve_at=validation.resolve_at,
                resolved_at=observed_at,
                entry_reference=validation.entry_reference,
                exit_reference=exit_reference,
                movement=compare_visual_references(
                    validation.entry_reference,
                    exit_reference,
                ),
                diagnostic=unresolved_diagnostic(
                    validation.entry_reference,
                    exit_reference,
                ),
                entry_visual_price_context=(
                    validation.entry_visual_price_context
                ),
                exit_visual_price_context=exit_visual_price_context,
            )
            for validation in due
        )
        for validation in due:
            del self._pending[validation.snapshot_id]
        return resolutions
