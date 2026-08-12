from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from pocket_option_analyzer.application.strategy import (
    StrategyObservationOutcome,
    StrategyObservationRecorder,
    StrategyObservationResolution,
    VisualPriceReference,
    VisualReferenceMovement,
    VisualReferenceResolution,
)
from pocket_option_analyzer.domain.signals import SignalDirection
from pocket_option_analyzer.vision.models import (
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

    resolutions = recorder.resolve_due(
        instant + timedelta(seconds=10),
        exit_reference,
        exit_current_visual_price=exit_extraction,
    )

    assert len(resolutions) == 1
    assert resolutions[0].outcome is expected_outcome
    assert resolutions[0].exit_current_visual_price is exit_extraction
    reference_resolution = next(
        item for item in writer.items if isinstance(item, VisualReferenceResolution)
    )
    assert reference_resolution.exit_current_visual_price is exit_extraction


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
