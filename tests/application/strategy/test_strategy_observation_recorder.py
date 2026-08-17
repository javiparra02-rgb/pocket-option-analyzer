from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from pocket_option_analyzer.application.strategy import (
    CurrentVisualPriceComparator,
    CurrentVisualPriceComparison,
    CurrentVisualPriceComparisonContext,
    CurrentVisualPriceComparisonDiagnostic,
    CurrentVisualPriceComparisonStatus,
    PriceMovement,
    StrategyObservation,
    StrategyObservationOutcome,
    StrategyObservationRecorder,
    StrategyObservationResolution,
    StrategyObservationResolutionBatch,
    VisualPriceMovementClassification,
    VisualPriceMovementClassificationDiagnostic,
    VisualPriceMovementClassifier,
    VisualPriceReference,
    VisualPriceReferenceResult,
    VisualPriceReferenceStatus,
    VisualReferenceMovement,
    VisualReferenceResolution,
    VisualReferenceValidationResolver,
)
from pocket_option_analyzer.domain.signals import SignalDirection
from pocket_option_analyzer.vision.models import (
    ChartRegion,
    CurrentVisualPrice,
    CurrentVisualPriceExtraction,
    CurrentVisualPriceStatus,
)

_ANCHORS = (
    ("bullish", 1.0, 0.8, 0.6, 0.4),
    ("bearish", 0.7, 0.5, 0.3, 0.0),
)


def _reference(value: float) -> VisualPriceReference:
    return VisualPriceReference(value, anchor_shape=_ANCHORS)


def _valid_extraction(
    roi_y: float = 514.0,
) -> CurrentVisualPriceExtraction:
    return CurrentVisualPriceExtraction(
        price=CurrentVisualPrice(
            roi_y,
            (799.0 - roi_y) / 799.0,
            1320,
            800,
            "test",
            0.92,
        ),
        status=CurrentVisualPriceStatus.OK,
        candidate_count=1,
        selected_x=1268.5,
        selected_y=514.0,
        confidence=0.92,
    )


def _failed_extraction() -> CurrentVisualPriceExtraction:
    return CurrentVisualPriceExtraction(
        price=None,
        status=CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE,
        diagnostic="no candidate matched the visual price mask",
    )


def _comparison_context(
    *,
    reference: VisualPriceReference | None,
    extraction: CurrentVisualPriceExtraction | None = None,
    region_offset: int = 0,
) -> CurrentVisualPriceComparisonContext:
    return CurrentVisualPriceComparisonContext(
        current_visual_price=extraction,
        chart_region=ChartRegion(
            x=20,
            y=30 + region_offset,
            width=1000,
            height=700,
        ),
        price_observation_region=ChartRegion(
            x=0,
            y=80 + region_offset,
            width=1320,
            height=800,
        ),
        reference_result=VisualPriceReferenceResult(
            reference=reference,
            status=(
                VisualPriceReferenceStatus.OK
                if reference is not None
                else VisualPriceReferenceStatus.LATEST_CANDLE_MISSING
            ),
            anchor_top_roi_y=100,
            anchor_bottom_roi_y=650,
        ),
    )


class _Writer:
    def __init__(self) -> None:
        self.items: list[object] = []

    def write(self, observation: object) -> None:
        self.items.append(observation)

    def write_resolution(self, resolution: object) -> None:
        self.items.append(resolution)

    def write_reference_validation(self, validation: object) -> None:
        self.items.append(validation)

    def write_reference_resolution(self, resolution: object) -> None:
        self.items.append(resolution)


class _SpyComparator(CurrentVisualPriceComparator):
    def __init__(self) -> None:
        self.calls: list[
            tuple[
                CurrentVisualPriceComparisonContext | None,
                CurrentVisualPriceComparisonContext | None,
            ]
        ] = []

    def compare(
        self,
        entry_context: CurrentVisualPriceComparisonContext | None,
        exit_context: CurrentVisualPriceComparisonContext | None,
    ) -> CurrentVisualPriceComparison:
        self.calls.append((entry_context, exit_context))
        return super().compare(entry_context, exit_context)


class _SpyMovementClassifier(VisualPriceMovementClassifier):
    def __init__(self, pixel_tolerance: float | None = None) -> None:
        super().__init__(pixel_tolerance)
        self.calls: list[CurrentVisualPriceComparison] = []

    def classify(
        self,
        comparison: CurrentVisualPriceComparison,
    ) -> VisualPriceMovementClassification:
        self.calls.append(comparison)
        return super().classify(comparison)


class _FixedMovementClassifier(VisualPriceMovementClassifier):
    def __init__(
        self,
        classification: VisualPriceMovementClassification,
    ) -> None:
        self._classification = classification

    def classify(
        self,
        comparison: CurrentVisualPriceComparison,
    ) -> VisualPriceMovementClassification:
        return self._classification


def _shadow_classification(
    movement: PriceMovement,
) -> VisualPriceMovementClassification:
    if movement is PriceMovement.UNRESOLVED:
        return VisualPriceMovementClassification(
            movement=movement,
            epsilon=None,
            pixel_tolerance=None,
            diagnostic=(
                VisualPriceMovementClassificationDiagnostic.EPSILON_NOT_CALIBRATED
            ),
        )
    return VisualPriceMovementClassification(
        movement=movement,
        epsilon=0.0,
        pixel_tolerance=0.0,
        diagnostic=VisualPriceMovementClassificationDiagnostic.CLASSIFIED,
    )


class _NoReferenceResolutionResolver(VisualReferenceValidationResolver):
    def add(self, observation: StrategyObservation) -> None:
        return None

    def resolve_due(
        self,
        observed_at: datetime,
        exit_reference: VisualPriceReference | None,
        exit_visual_price_context: CurrentVisualPriceComparisonContext
        | None = None,
    ) -> tuple[VisualReferenceResolution, ...]:
        return ()


def _observation(instant: datetime) -> SimpleNamespace:
    return SimpleNamespace(
        observed_at=instant,
        candle_interval_started_at=instant,
        resolve_at=instant + timedelta(seconds=10),
        direction=SignalDirection.CALL,
        entry_reference=_reference(100.0),
        entry_reference_result=None,
        current_visual_price=None,
    )


def test_recorder_persists_only_once_per_snapshot() -> None:
    writer = _Writer()
    recorder = StrategyObservationRecorder(writer=writer)
    observation = _observation(datetime(2026, 8, 9, tzinfo=UTC))

    assert recorder.record(observation) is True
    assert recorder.record(observation) is False
    assert writer.items[0] is observation
    assert writer.items[1].entry_reference == observation.entry_reference


def test_recorder_marks_snapshot_seen_only_after_successful_write() -> None:
    class FailingWriter:
        def __init__(self) -> None:
            self.calls = 0

        def write(self, observation: object) -> None:
            self.calls += 1
            if self.calls == 1:
                raise OSError("disk unavailable")

        def write_resolution(self, resolution: object) -> None:
            pass

        def write_reference_validation(self, validation: object) -> None:
            pass

        def write_reference_resolution(self, resolution: object) -> None:
            pass

    observation = _observation(datetime(2026, 8, 9, tzinfo=UTC))
    writer = FailingWriter()
    recorder = StrategyObservationRecorder(writer=writer)

    try:
        recorder.record(observation)
    except OSError:
        pass

    assert recorder.record(observation) is True
    assert writer.calls == 2


def test_recorder_resolves_once_on_first_frame_at_or_after_target() -> None:
    instant = datetime(2026, 8, 9, tzinfo=UTC)
    writer = _Writer()
    recorder = StrategyObservationRecorder(writer=writer)
    observation = _observation(instant)
    recorder.record(observation)

    assert (
        recorder.resolve_due(
            instant + timedelta(seconds=9),
            _reference(101.0),
        )
        == ()
    )
    exit_extraction = _valid_extraction()
    resolutions = recorder.resolve_due(
        instant + timedelta(seconds=11),
        _reference(101.0),
        exit_current_visual_price=exit_extraction,
    )
    assert len(resolutions) == 1
    assert resolutions[0].outcome is StrategyObservationOutcome.WIN
    assert resolutions[0].exit_current_visual_price is exit_extraction
    assert writer.items[-1].movement is VisualReferenceMovement.UP
    assert writer.items[-1].exit_current_visual_price is exit_extraction
    assert (
        recorder.resolve_due(
            instant + timedelta(seconds=12),
            _reference(102.0),
        )
        == ()
    )


def test_reference_validation_works_with_direction_none_and_resolves_once() -> None:
    instant = datetime(2026, 8, 9, tzinfo=UTC)
    writer = _Writer()
    recorder = StrategyObservationRecorder(writer=writer)
    observation = _observation(instant)
    observation.direction = None
    recorder.record(observation)

    assert recorder.resolve_due(instant + timedelta(seconds=9), _reference(101.0)) == ()
    assert (
        recorder.resolve_due(instant + timedelta(seconds=10), _reference(101.0)) == ()
    )
    assert writer.items[-1].movement is VisualReferenceMovement.UP
    item_count = len(writer.items)
    assert (
        recorder.resolve_due(instant + timedelta(seconds=11), _reference(102.0)) == ()
    )
    assert len(writer.items) == item_count


@pytest.mark.parametrize(
    ("exit_reference", "expected_outcome"),
    [
        (_reference(101.0), StrategyObservationOutcome.WIN),
        (_reference(99.0), StrategyObservationOutcome.LOSS),
        (None, StrategyObservationOutcome.UNRESOLVED),
    ],
)
def test_exit_visual_price_does_not_change_existing_outcome_resolution(
    exit_reference: VisualPriceReference | None,
    expected_outcome: StrategyObservationOutcome,
) -> None:
    instant = datetime(2026, 8, 9, tzinfo=UTC)
    writer = _Writer()
    recorder = StrategyObservationRecorder(writer=writer)
    observation = _observation(instant)
    observation.visual_price_comparison_context = _comparison_context(
        reference=observation.entry_reference,
        extraction=_valid_extraction(),
    )
    recorder.record(observation)
    exit_extraction = _failed_extraction()
    exit_context = _comparison_context(
        reference=exit_reference,
        extraction=exit_extraction,
    )

    resolutions = recorder.resolve_due(
        instant + timedelta(seconds=10),
        exit_reference,
        exit_current_visual_price=exit_extraction,
        exit_visual_price_context=exit_context,
    )

    assert len(resolutions) == 1
    assert resolutions[0].outcome is expected_outcome
    assert (
        resolutions[0].exit_reference
        is exit_context.reference_result.reference
    )
    assert resolutions[0].exit_current_visual_price is exit_context.current_visual_price
    assert resolutions[0].exit_visual_price_context is exit_context
    assert (
        resolutions[0].visual_price_comparison.status
        is CurrentVisualPriceComparisonStatus.UNAVAILABLE
    )
    assert (
        resolutions[0].visual_price_comparison.diagnostic
        is CurrentVisualPriceComparisonDiagnostic.EXIT_EXTRACTION_UNAVAILABLE
    )
    assert (
        resolutions[0].visual_price_movement_classification.diagnostic
        is VisualPriceMovementClassificationDiagnostic.COMPARISON_UNAVAILABLE
    )
    reference_resolution = next(
        item for item in writer.items if isinstance(item, VisualReferenceResolution)
    )
    assert (
        reference_resolution.exit_reference
        is exit_context.reference_result.reference
    )
    assert (
        reference_resolution.exit_current_visual_price
        is exit_context.current_visual_price
    )
    assert reference_resolution.exit_visual_price_context is exit_context
    assert (
        reference_resolution.visual_price_movement_classification
        is resolutions[0].visual_price_movement_classification
    )


def test_contexts_remain_associated_with_each_snapshot_on_shared_exit() -> None:
    first_instant = datetime(2026, 8, 9, tzinfo=UTC)
    second_instant = first_instant + timedelta(seconds=5)
    entry_reference = _reference(100.0)
    exit_reference = _reference(101.0)
    exit_extraction = _valid_extraction()
    first_context = _comparison_context(
        reference=entry_reference,
        extraction=_valid_extraction(500.0),
        region_offset=10,
    )
    second_context = _comparison_context(
        reference=entry_reference,
        extraction=_valid_extraction(550.0),
        region_offset=20,
    )
    exit_context = _comparison_context(
        reference=exit_reference,
        extraction=exit_extraction,
        region_offset=30,
    )
    first_observation = _observation(first_instant)
    second_observation = _observation(second_instant)
    first_observation.entry_reference = entry_reference
    second_observation.entry_reference = entry_reference
    first_observation.visual_price_comparison_context = first_context
    second_observation.visual_price_comparison_context = second_context
    writer = _Writer()
    spy = _SpyComparator()
    movement_spy = _SpyMovementClassifier()
    recorder = StrategyObservationRecorder(
        writer=writer,
        visual_price_comparator=spy,
        visual_price_movement_classifier=movement_spy,
    )
    recorder.record(first_observation)
    recorder.record(second_observation)

    resolutions = recorder.resolve_due(
        second_instant + timedelta(seconds=10),
        exit_reference,
        exit_current_visual_price=exit_extraction,
        exit_visual_price_context=exit_context,
    )

    assert [resolution.snapshot_id for resolution in resolutions] == [
        first_instant.isoformat(),
        second_instant.isoformat(),
    ]
    assert resolutions[0].entry_visual_price_context is first_context
    assert resolutions[1].entry_visual_price_context is second_context
    assert all(
        resolution.exit_visual_price_context is exit_context
        for resolution in resolutions
    )
    assert all(
        resolution.exit_reference is exit_context.reference_result.reference
        for resolution in resolutions
    )
    assert all(
        resolution.exit_current_visual_price is exit_context.current_visual_price
        for resolution in resolutions
    )
    assert all(
        resolution.visual_price_comparison.status
        is CurrentVisualPriceComparisonStatus.AVAILABLE
        for resolution in resolutions
    )
    assert (
        resolutions[0].visual_price_comparison.entry_anchored_value
        != resolutions[1].visual_price_comparison.entry_anchored_value
    )
    assert (
        resolutions[0].visual_price_comparison.exit_anchored_value
        == resolutions[1].visual_price_comparison.exit_anchored_value
    )
    reference_resolutions = [
        item for item in writer.items if isinstance(item, VisualReferenceResolution)
    ]
    assert reference_resolutions[0].entry_visual_price_context is first_context
    assert reference_resolutions[1].entry_visual_price_context is second_context
    assert all(
        resolution.exit_visual_price_context is exit_context
        for resolution in reference_resolutions
    )
    assert all(
        resolution.exit_reference is exit_context.reference_result.reference
        for resolution in reference_resolutions
    )
    assert all(
        resolution.exit_current_visual_price is exit_context.current_visual_price
        for resolution in reference_resolutions
    )
    assert all(
        reference_resolution.visual_price_comparison
        is strategy_resolution.visual_price_comparison
        for strategy_resolution, reference_resolution in zip(
            resolutions,
            reference_resolutions,
            strict=True,
        )
    )
    assert all(
        reference_resolution.visual_price_movement_classification
        is strategy_resolution.visual_price_movement_classification
        for strategy_resolution, reference_resolution in zip(
            resolutions,
            reference_resolutions,
            strict=True,
        )
    )
    assert spy.calls == [
        (first_context, exit_context),
        (second_context, exit_context),
    ]
    assert movement_spy.calls == [
        resolutions[0].visual_price_comparison,
        resolutions[1].visual_price_comparison,
    ]


def test_recorder_compares_once_and_shares_result_between_resolution_dtos() -> None:
    instant = datetime(2026, 8, 9, tzinfo=UTC)
    observation = _observation(instant)
    entry_context = _comparison_context(
        reference=observation.entry_reference,
        extraction=_valid_extraction(),
    )
    observation.visual_price_comparison_context = entry_context
    exit_reference = _reference(101.0)
    exit_extraction = _valid_extraction(450.0)
    exit_context = _comparison_context(
        reference=exit_reference,
        extraction=exit_extraction,
    )
    spy = _SpyComparator()
    movement_spy = _SpyMovementClassifier()
    writer = _Writer()
    recorder = StrategyObservationRecorder(
        writer=writer,
        visual_price_comparator=spy,
        visual_price_movement_classifier=movement_spy,
    )
    recorder.record(observation)

    strategy_resolution = recorder.resolve_due(
        instant + timedelta(seconds=10),
        exit_reference,
        exit_current_visual_price=exit_extraction,
        exit_visual_price_context=exit_context,
    )[0]
    reference_resolution = next(
        item for item in writer.items if isinstance(item, VisualReferenceResolution)
    )

    assert spy.calls == [(entry_context, exit_context)]
    assert movement_spy.calls == [strategy_resolution.visual_price_comparison]
    assert (
        strategy_resolution.visual_price_comparison
        is reference_resolution.visual_price_comparison
    )
    assert (
        strategy_resolution.visual_price_movement_classification
        is reference_resolution.visual_price_movement_classification
    )


def test_recorder_compares_once_when_only_primary_resolution_exists() -> None:
    instant = datetime(2026, 8, 9, tzinfo=UTC)
    observation = _observation(instant)
    entry_context = _comparison_context(
        reference=observation.entry_reference,
        extraction=_valid_extraction(),
    )
    observation.visual_price_comparison_context = entry_context
    exit_reference = _reference(101.0)
    exit_extraction = _valid_extraction(450.0)
    exit_context = _comparison_context(
        reference=exit_reference,
        extraction=exit_extraction,
    )
    spy = _SpyComparator()
    movement_spy = _SpyMovementClassifier()
    recorder = StrategyObservationRecorder(
        reference_resolver=_NoReferenceResolutionResolver(),
        visual_price_comparator=spy,
        visual_price_movement_classifier=movement_spy,
    )
    recorder.record(observation)

    resolutions = recorder.resolve_due(
        instant + timedelta(seconds=10),
        exit_reference,
        exit_current_visual_price=exit_extraction,
        exit_visual_price_context=exit_context,
    )

    assert len(resolutions) == 1
    assert spy.calls == [(entry_context, exit_context)]
    assert movement_spy.calls == [resolutions[0].visual_price_comparison]


@pytest.mark.parametrize(
    ("exit_reference", "exit_roi_y", "expected_outcome", "expected_delta"),
    [
        (_reference(101.0), 450.0, StrategyObservationOutcome.WIN, 64 / 550),
        (_reference(99.0), 578.0, StrategyObservationOutcome.LOSS, -64 / 550),
        (_reference(100.0), 514.0, StrategyObservationOutcome.DRAW, 0.0),
    ],
)
def test_visual_delta_does_not_change_legacy_outcome(
    exit_reference: VisualPriceReference,
    exit_roi_y: float,
    expected_outcome: StrategyObservationOutcome,
    expected_delta: float,
) -> None:
    instant = datetime(2026, 8, 9, tzinfo=UTC)
    observation = _observation(instant)
    observation.visual_price_comparison_context = _comparison_context(
        reference=observation.entry_reference,
        extraction=_valid_extraction(514.0),
    )
    exit_extraction = _valid_extraction(exit_roi_y)
    exit_context = _comparison_context(
        reference=exit_reference,
        extraction=exit_extraction,
    )
    recorder = StrategyObservationRecorder()
    recorder.record(observation)

    resolutions = recorder.resolve_due(
        instant + timedelta(seconds=10),
        exit_reference,
        exit_current_visual_price=exit_extraction,
        exit_visual_price_context=exit_context,
    )

    assert resolutions[0].outcome is expected_outcome
    assert resolutions[0].visual_price_comparison.delta == pytest.approx(
        expected_delta,
    )
    assert (
        resolutions[0].visual_price_movement_classification.movement
        is PriceMovement.UNRESOLVED
    )
    assert (
        resolutions[0].visual_price_movement_classification.diagnostic
        is VisualPriceMovementClassificationDiagnostic.EPSILON_NOT_CALIBRATED
    )


@pytest.mark.parametrize(
    (
        "direction",
        "exit_reference",
        "shadow_movement",
        "expected_outcome",
    ),
    (
        (
            SignalDirection.CALL,
            _reference(101.0),
            PriceMovement.DOWN,
            StrategyObservationOutcome.WIN,
        ),
        (
            SignalDirection.CALL,
            _reference(101.0),
            PriceMovement.FLAT,
            StrategyObservationOutcome.WIN,
        ),
        (
            SignalDirection.CALL,
            _reference(99.0),
            PriceMovement.UP,
            StrategyObservationOutcome.LOSS,
        ),
        (
            SignalDirection.PUT,
            _reference(99.0),
            PriceMovement.FLAT,
            StrategyObservationOutcome.WIN,
        ),
        (
            SignalDirection.PUT,
            _reference(101.0),
            PriceMovement.UNRESOLVED,
            StrategyObservationOutcome.LOSS,
        ),
        (
            SignalDirection.CALL,
            _reference(100.0),
            PriceMovement.UP,
            StrategyObservationOutcome.DRAW,
        ),
        (
            SignalDirection.CALL,
            None,
            PriceMovement.DOWN,
            StrategyObservationOutcome.UNRESOLVED,
        ),
    ),
)
def test_shadow_classification_never_changes_legacy_outcome(
    direction: SignalDirection,
    exit_reference: VisualPriceReference | None,
    shadow_movement: PriceMovement,
    expected_outcome: StrategyObservationOutcome,
) -> None:
    instant = datetime(2026, 8, 9, tzinfo=UTC)
    observation = _observation(instant)
    observation.direction = direction
    classification = _shadow_classification(shadow_movement)
    recorder = StrategyObservationRecorder(
        visual_price_movement_classifier=(
            _FixedMovementClassifier(classification)
        ),
    )
    recorder.record(observation)

    resolution = recorder.resolve_due(
        instant + timedelta(seconds=10),
        exit_reference,
    )[0]

    assert resolution.outcome is expected_outcome
    assert resolution.visual_price_movement_classification is classification


def test_reference_resolution_keeps_comparison_without_primary_resolution() -> None:
    instant = datetime(2026, 8, 9, tzinfo=UTC)
    observation = _observation(instant)
    observation.direction = None
    observation.visual_price_comparison_context = _comparison_context(
        reference=observation.entry_reference,
        extraction=_valid_extraction(),
    )
    exit_reference = _reference(101.0)
    exit_extraction = _valid_extraction(450.0)
    exit_context = _comparison_context(
        reference=exit_reference,
        extraction=exit_extraction,
    )
    writer = _Writer()
    spy = _SpyComparator()
    movement_spy = _SpyMovementClassifier()
    recorder = StrategyObservationRecorder(
        writer=writer,
        visual_price_comparator=spy,
        visual_price_movement_classifier=movement_spy,
    )
    recorder.record(observation)

    primary = recorder.resolve_due(
        instant + timedelta(seconds=10),
        exit_reference,
        exit_current_visual_price=exit_extraction,
        exit_visual_price_context=exit_context,
    )

    assert primary == ()
    reference_resolution = next(
        item for item in writer.items if isinstance(item, VisualReferenceResolution)
    )
    assert (
        reference_resolution.visual_price_comparison.status
        is CurrentVisualPriceComparisonStatus.AVAILABLE
    )
    assert spy.calls == [(observation.visual_price_comparison_context, exit_context)]
    assert movement_spy.calls == [reference_resolution.visual_price_comparison]


def test_recorder_derives_missing_exit_evidence_from_canonical_context() -> None:
    instant = datetime(2026, 8, 9, tzinfo=UTC)
    exit_context = _comparison_context(
        reference=_reference(101.0),
        extraction=_valid_extraction(),
    )
    writer = _Writer()
    recorder = StrategyObservationRecorder(writer=writer)
    recorder.record(_observation(instant))

    resolutions = recorder.resolve_due(
        instant + timedelta(seconds=10),
        None,
        exit_visual_price_context=exit_context,
    )

    assert len(resolutions) == 1
    assert resolutions[0].outcome is StrategyObservationOutcome.WIN
    assert resolutions[0].exit_reference is exit_context.reference_result.reference
    assert resolutions[0].exit_current_visual_price is exit_context.current_visual_price


@pytest.mark.parametrize(
    ("exit_reference", "exit_extraction", "message"),
    [
        (_reference(99.0), _valid_extraction(), "exit_reference"),
        (_reference(101.0), _failed_extraction(), "exit_current_visual_price"),
    ],
)
def test_recorder_rejects_exit_evidence_that_contradicts_canonical_context(
    exit_reference: VisualPriceReference,
    exit_extraction: CurrentVisualPriceExtraction,
    message: str,
) -> None:
    instant = datetime(2026, 8, 9, tzinfo=UTC)
    exit_context = _comparison_context(
        reference=_reference(101.0),
        extraction=_valid_extraction(),
    )
    recorder = StrategyObservationRecorder(writer=_Writer())

    with pytest.raises(ValueError, match=message):
        recorder.resolve_due(
            instant,
            exit_reference,
            exit_current_visual_price=exit_extraction,
            exit_visual_price_context=exit_context,
        )


def test_exit_visual_price_is_associated_with_each_due_snapshot() -> None:
    first_instant = datetime(2026, 8, 9, tzinfo=UTC)
    second_instant = first_instant + timedelta(seconds=5)
    writer = _Writer()
    recorder = StrategyObservationRecorder(writer=writer)
    recorder.record(_observation(first_instant))
    recorder.record(_observation(second_instant))
    first_extraction = _valid_extraction()
    second_extraction = _failed_extraction()

    recorder.resolve_due(
        first_instant + timedelta(seconds=11),
        _reference(101.0),
        exit_current_visual_price=first_extraction,
    )
    recorder.resolve_due(
        second_instant + timedelta(seconds=11),
        _reference(102.0),
        exit_current_visual_price=second_extraction,
    )

    resolutions = [
        item for item in writer.items if isinstance(item, StrategyObservationResolution)
    ]
    assert [resolution.snapshot_id for resolution in resolutions] == [
        first_instant.isoformat(),
        second_instant.isoformat(),
    ]
    assert resolutions[0].exit_current_visual_price is first_extraction
    assert resolutions[1].exit_current_visual_price is second_extraction


def test_resolution_report_includes_reference_only_snapshot() -> None:
    instant = datetime(2026, 8, 9, tzinfo=UTC)
    observation = _observation(instant)
    observation.direction = None
    recorder = StrategyObservationRecorder()
    recorder.record(observation)

    report = recorder.resolve_due_with_report(
        instant + timedelta(seconds=10),
        _reference(101.0),
    )

    assert isinstance(report, StrategyObservationResolutionBatch)
    assert report.resolutions == ()
    assert len(report.reference_resolutions) == 1
    assert report.reference_resolutions[0].snapshot_id == instant.isoformat()


def test_legacy_resolve_due_return_remains_primary_only() -> None:
    instant = datetime(2026, 8, 9, tzinfo=UTC)
    observation = _observation(instant)
    observation.direction = None
    writer = _Writer()
    recorder = StrategyObservationRecorder(writer=writer)
    recorder.record(observation)

    primary = recorder.resolve_due(
        instant + timedelta(seconds=10),
        _reference(101.0),
    )

    assert primary == ()
    assert any(isinstance(item, VisualReferenceResolution) for item in writer.items)
