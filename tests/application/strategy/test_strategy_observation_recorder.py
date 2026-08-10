from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from pocket_option_analyzer.application.strategy import (
    StrategyObservationOutcome,
    StrategyObservationRecorder,
    VisualPriceReference,
    VisualReferenceMovement,
)
from pocket_option_analyzer.domain.signals import SignalDirection

_ANCHORS = (
    ("bullish", 1.0, 0.8, 0.6, 0.4),
    ("bearish", 0.7, 0.5, 0.3, 0.0),
)


def _reference(value: float) -> VisualPriceReference:
    return VisualPriceReference(value, anchor_shape=_ANCHORS)


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
    resolutions = recorder.resolve_due(
        instant + timedelta(seconds=11),
        _reference(101.0),
    )
    assert len(resolutions) == 1
    assert resolutions[0].outcome is StrategyObservationOutcome.WIN
    assert writer.items[-1].movement is VisualReferenceMovement.UP
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
