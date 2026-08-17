from __future__ import annotations

from dataclasses import dataclass, replace
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
from pocket_option_analyzer.vision.models import CurrentVisualPriceExtraction

from .current_visual_price_comparator import CurrentVisualPriceComparator
from .current_visual_price_comparison import CurrentVisualPriceComparison
from .current_visual_price_comparison_context import (
    CurrentVisualPriceComparisonContext,
)
from .visual_price_movement_classification import (
    VisualPriceMovementClassification,
)
from .visual_price_movement_classifier import VisualPriceMovementClassifier


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


@dataclass(frozen=True, slots=True)
class StrategyObservationResolutionBatch:
    """Complete set of primary and reference resolutions for one frame."""

    resolutions: tuple[StrategyObservationResolution, ...]
    reference_resolutions: tuple[VisualReferenceResolution, ...]


class StrategyObservationRecorder:
    """Persists at most one observation for each stable candle snapshot."""

    def __init__(
        self,
        writer: StrategyObservationWriter | None = None,
        resolver: StrategyObservationOutcomeResolver | None = None,
        reference_resolver: VisualReferenceValidationResolver | None = None,
        visual_price_comparator: CurrentVisualPriceComparator | None = None,
        visual_price_movement_classifier: VisualPriceMovementClassifier
        | None = None,
    ) -> None:
        self._writer = writer
        self._resolver = resolver or StrategyObservationOutcomeResolver()
        self._reference_resolver = (
            reference_resolver or VisualReferenceValidationResolver()
        )
        self._visual_price_comparator = (
            visual_price_comparator or CurrentVisualPriceComparator()
        )
        self._visual_price_movement_classifier = (
            visual_price_movement_classifier or VisualPriceMovementClassifier()
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
        exit_current_visual_price: CurrentVisualPriceExtraction | None = None,
        exit_visual_price_context: CurrentVisualPriceComparisonContext
        | None = None,
    ) -> tuple[StrategyObservationResolution, ...]:
        """Resolve due observations while preserving the legacy public result."""

        return self.resolve_due_with_report(
            observed_at=observed_at,
            exit_reference=exit_reference,
            exit_current_visual_price=exit_current_visual_price,
            exit_visual_price_context=exit_visual_price_context,
        ).resolutions

    def resolve_due_with_report(
        self,
        observed_at: datetime,
        exit_reference: VisualPriceReference | None,
        exit_current_visual_price: CurrentVisualPriceExtraction | None = None,
        exit_visual_price_context: CurrentVisualPriceComparisonContext
        | None = None,
    ) -> StrategyObservationResolutionBatch:
        """Return every resolution emitted for the analyzed exit frame."""

        exit_reference, exit_current_visual_price = (
            self._canonical_exit_evidence(
                exit_reference=exit_reference,
                exit_current_visual_price=exit_current_visual_price,
                exit_visual_price_context=exit_visual_price_context,
            )
        )
        legacy_resolutions = self._resolver.resolve_due(
            observed_at,
            exit_reference,
            exit_visual_price_context,
        )
        legacy_reference_resolutions = self._reference_resolver.resolve_due(
            observed_at,
            exit_reference,
            exit_visual_price_context,
        )
        comparisons: dict[str, CurrentVisualPriceComparison] = {}
        classifications: dict[str, VisualPriceMovementClassification] = {}
        context_pairs: dict[
            str,
            tuple[
                CurrentVisualPriceComparisonContext | None,
                CurrentVisualPriceComparisonContext | None,
            ],
        ] = {}
        for resolution in (*legacy_resolutions, *legacy_reference_resolutions):
            pair = (
                resolution.entry_visual_price_context,
                resolution.exit_visual_price_context,
            )
            existing_pair = context_pairs.get(resolution.snapshot_id)
            if existing_pair is not None and existing_pair != pair:
                raise ValueError(
                    "Las resoluciones del mismo snapshot deben compartir "
                    "contextos visuales."
                )
            if resolution.snapshot_id not in comparisons:
                context_pairs[resolution.snapshot_id] = pair
                comparison = self._visual_price_comparator.compare(*pair)
                comparisons[resolution.snapshot_id] = comparison
                classifications[resolution.snapshot_id] = (
                    self._visual_price_movement_classifier.classify(comparison)
                )

        resolutions = tuple(
            replace(
                resolution,
                exit_current_visual_price=exit_current_visual_price,
                visual_price_comparison=comparisons[resolution.snapshot_id],
                visual_price_movement_classification=(
                    classifications[resolution.snapshot_id]
                ),
            )
            for resolution in legacy_resolutions
        )
        reference_resolutions = tuple(
            replace(
                resolution,
                exit_current_visual_price=exit_current_visual_price,
                visual_price_comparison=comparisons[resolution.snapshot_id],
                visual_price_movement_classification=(
                    classifications[resolution.snapshot_id]
                ),
            )
            for resolution in legacy_reference_resolutions
        )
        if self._writer is not None:
            for resolution in resolutions:
                self._writer.write_resolution(resolution)
            for resolution in reference_resolutions:
                self._writer.write_reference_resolution(resolution)
        return StrategyObservationResolutionBatch(
            resolutions=resolutions,
            reference_resolutions=reference_resolutions,
        )

    @staticmethod
    def _canonical_exit_evidence(
        *,
        exit_reference: VisualPriceReference | None,
        exit_current_visual_price: CurrentVisualPriceExtraction | None,
        exit_visual_price_context: CurrentVisualPriceComparisonContext | None,
    ) -> tuple[
        VisualPriceReference | None,
        CurrentVisualPriceExtraction | None,
    ]:
        if exit_visual_price_context is None:
            return exit_reference, exit_current_visual_price

        canonical_reference = (
            exit_visual_price_context.reference_result.reference
        )
        canonical_visual_price = (
            exit_visual_price_context.current_visual_price
        )
        if (
            exit_reference is not None
            and exit_reference != canonical_reference
        ):
            raise ValueError(
                "exit_reference debe coincidir con exit_visual_price_context."
            )
        if (
            exit_current_visual_price is not None
            and exit_current_visual_price != canonical_visual_price
        ):
            raise ValueError(
                "exit_current_visual_price debe coincidir con "
                "exit_visual_price_context."
            )
        return canonical_reference, canonical_visual_price
