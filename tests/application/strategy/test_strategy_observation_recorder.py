from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from pocket_option_analyzer.application.strategy import (
    CurrentVisualPriceComparisonContext,
    StrategyObservationOutcome,
    StrategyObservationRecorder,
    StrategyObservationResolution,
    VisualPriceReference,
    VisualPriceReferenceResult,
    VisualPriceReferenceStatus,
    VisualReferenceMovement,
    VisualReferenceResolution,
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


def _valid_extraction() -> CurrentVisualPriceExtraction:
    return CurrentVisualPriceExtraction(
        price=CurrentVisualPrice(514.0, 0.73125, 1320, 800, "test", 0.92),
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
            anchor_bottom_roi_y=700,
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
    recorder.record(_observation(instant))
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


def test_contexts_remain_associated_with_each_snapshot_on_shared_exit() -> None:
    first_instant = datetime(2026, 8, 9, tzinfo=UTC)
    second_instant = first_instant + timedelta(seconds=5)
    entry_reference = _reference(100.0)
    exit_reference = _reference(101.0)
    exit_extraction = _valid_extraction()
    first_context = _comparison_context(
        reference=entry_reference,
        region_offset=10,
    )
    second_context = _comparison_context(
        reference=entry_reference,
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
    recorder = StrategyObservationRecorder(writer=writer)
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
