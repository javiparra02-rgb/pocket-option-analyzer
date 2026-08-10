from datetime import UTC, datetime

from pocket_option_analyzer.application.strategy import StrategyObservationRecorder


class _Writer:
    def __init__(self) -> None:
        self.items: list[object] = []

    def write(self, observation: object) -> None:
        self.items.append(observation)


def test_recorder_persists_only_once_per_snapshot() -> None:
    writer = _Writer()
    recorder = StrategyObservationRecorder(writer=writer)
    observation = type(
        "Observation",
        (),
        {"candle_interval_started_at": datetime(2026, 8, 9, tzinfo=UTC)},
    )()

    assert recorder.record(observation) is True
    assert recorder.record(observation) is False
    assert writer.items == [observation]


def test_recorder_marks_snapshot_seen_only_after_successful_write() -> None:
    class FailingWriter:
        def __init__(self) -> None:
            self.calls = 0

        def write(self, observation: object) -> None:
            self.calls += 1
            if self.calls == 1:
                raise OSError("disk unavailable")

    observation = type(
        "Observation",
        (),
        {"candle_interval_started_at": datetime(2026, 8, 9, tzinfo=UTC)},
    )()
    writer = FailingWriter()
    recorder = StrategyObservationRecorder(writer=writer)

    try:
        recorder.record(observation)
    except OSError:
        pass

    assert recorder.record(observation) is True
    assert writer.calls == 2
