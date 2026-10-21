from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import numpy as np
import pytest

from pocket_option_analyzer.application.market import (
    CandleIntervalIndicatorCacheStatus,
    VisualIndicatorSnapshotContext,
)
from pocket_option_analyzer.application.signals import (
    ActionableSignalGate,
    SignalRecorder,
    StrategySignalGenerator,
    VisualSignalRecordingPipeline,
    VisualStrategySignalAnalysisPipeline,
)
from pocket_option_analyzer.application.signals.accepted_signal_evidence import (
    AcceptedSignalEvidenceRecorder,
    json_snapshot,
)
from pocket_option_analyzer.application.strategy import (
    StrategyConditionEvaluator,
    StrategyObservationRecorder,
)
from pocket_option_analyzer.application.timing import CandleIntervalKey
from pocket_option_analyzer.domain.indicators import (
    EmaSnapshot,
    IndicatorSnapshot,
    RsiSnapshot,
    StochasticSnapshot,
)
from pocket_option_analyzer.domain.signals import (
    SignalDirection,
    SignalHistory,
    SignalRecordDisposition,
)
from pocket_option_analyzer.domain.strategy import StrategyProfile
from pocket_option_analyzer.infrastructure.signals import (
    JsonlSignalRecordWriter,
    JsonlStrategyObservationWriter,
)
from pocket_option_analyzer.infrastructure.signals.signal_record_serializer import (
    SignalRecordSerializer,
)
from pocket_option_analyzer.vision.models import (
    CandleCandidate,
    CandleSeries,
    CandleType,
    ClassifiedCandle,
    MarketAnalysis,
    TrendDirection,
)

IMAGE = np.zeros((20, 20, 3), dtype=np.uint8)
BASE = datetime(2026, 8, 10, 6, 1, tzinfo=UTC)


def at(seconds):
    return BASE + timedelta(seconds=seconds)


class _Evaluator(StrategyConditionEvaluator):
    def __init__(self):
        super().__init__()
        self.calls = 0

    def audit(self, *args, **kwargs):
        self.calls += 1
        return super().audit(*args, **kwargs)


class _Market:
    def __init__(self, direction):
        self.trend = TrendDirection.SIDEWAYS
        self.direction = direction

    def analyze(self, **kwargs):
        kind = CandleType.BULLISH if self.direction == "call" else CandleType.BEARISH
        return MarketAnalysis(
            series=CandleSeries(
                candles=tuple(
                    ClassifiedCandle(CandleCandidate(x, 10, 4, 6, 24), kind)
                    for x in (1, 6, 11, 16)
                )
            ),
            trend=self.trend,
        )


class _Indicators:
    def __init__(self, direction):
        self.calls = 0
        self.snapshot_context = VisualIndicatorSnapshotContext(4, 3, 0, 3)
        key = CandleIntervalKey(BASE, 30)
        self.snapshot_timing_status = CandleIntervalIndicatorCacheStatus(
            key, key, True, True, False
        )
        self.value = (
            IndicatorSnapshot(
                EmaSnapshot(200.1234567890123, 100.0, 4),
                RsiSnapshot(55.1234567890123),
                StochasticSnapshot(35.0, 30.0, 20.0, 25.0),
            )
            if direction == "call"
            else IndicatorSnapshot(
                EmaSnapshot(100.0, 200.0, 4),
                RsiSnapshot(40.0),
                StochasticSnapshot(60.0, 70.0, 80.0, 75.0),
            )
        )

    def build(self, **kwargs):
        self.calls += 1
        return self.value


class _SignalWriter:
    def __init__(self):
        self.events = []
        self.attempts = []
        self.fail = False

    def write(self, record):
        pass

    def write_accepted(self, record, evidence):
        self.attempts.append((record, evidence))
        if self.fail:
            raise OSError("signal write failed")
        self.events.append(evidence.to_dict())


class _StrategyWriter:
    def __init__(self):
        self.observations = []
        self.exits = []
        self.exit_attempts = []
        self.fail = False

    def write(self, observation):
        self.observations.append(observation)

    def write_resolution(self, resolution):
        pass

    def write_reference_validation(self, validation):
        pass

    def write_reference_resolution(self, resolution):
        pass

    def write_accepted_exit(self, evidence):
        self.exit_attempts.append(evidence)
        if self.fail:
            raise OSError("exit write failed")
        self.exits.append(evidence.to_dict())


def setup(direction="call", signal_writer=None, strategy_writer=None):
    market = _Market(direction)
    indicators = _Indicators(direction)
    evaluator = _Evaluator()
    profile = StrategyProfile.otc_precision_10s()
    analysis = VisualStrategySignalAnalysisPipeline(
        market,
        indicators,
        StrategySignalGenerator(profile, evaluator),
        profile,
    )
    sw = signal_writer if signal_writer is not None else _SignalWriter()
    ow = strategy_writer if strategy_writer is not None else _StrategyWriter()
    pipeline = VisualSignalRecordingPipeline(
        analysis,
        SignalRecorder(SignalHistory()),
        record_writer=sw,
        observation_recorder=StrategyObservationRecorder(writer=ow),
        clock=lambda: at(100),
    )
    return SimpleNamespace(
        pipeline=pipeline,
        market=market,
        indicators=indicators,
        evaluator=evaluator,
        signals=sw,
        observations=ow,
    )


def analyze(test, seconds, frame_id=1, **kwargs):
    return test.pipeline.analyze_and_record(
        IMAGE,
        created_at=at(seconds),
        frame_id=frame_id,
        monotonic_timestamp=float(seconds),
        source_key="synthetic",
        session_key="fixture-session",
        **kwargs,
    )


def enable(test):
    test.market.trend = (
        TrendDirection.BULLISH
        if test.market.direction == "call"
        else TrendDirection.BEARISH
    )


@pytest.mark.parametrize("direction", ["call", "put"])
def test_neutral_then_accepted_has_own_exact_evidence(direction):
    test = setup(direction)
    neutral = analyze(test, 2.263493)
    enable(test)
    accepted = analyze(test, 17.245677, 2)
    event = test.signals.events[0]
    assert neutral.signal.direction is SignalDirection.NONE
    assert accepted.disposition is SignalRecordDisposition.ACTIONABLE_ACCEPTED
    assert len(test.observations.observations) == 1
    assert test.observations.observations[0].direction is None
    assert event["evaluation"]["observed_at"] == at(17.245677).isoformat()
    assert event["evaluation"]["audit"][direction]["passed_count"] == 7
    assert event["nominal_resolve_at"] == at(27.245677).isoformat()
    assert test.evaluator.calls == test.indicators.calls == 2


def test_duplicate_does_not_create_another_acceptance_or_change_gate():
    test = setup()
    enable(test)
    first = analyze(test, 2)
    duplicate = analyze(test, 3, 2)
    assert first.disposition is SignalRecordDisposition.ACTIONABLE_ACCEPTED
    assert duplicate.disposition is SignalRecordDisposition.DUPLICATE_SUPPRESSED
    assert len(test.signals.events) == 1
    assert test.evaluator.calls == 2


def test_context_is_detached_and_cached_provenance_is_not_current_frame():
    test = setup()
    enable(test)
    analyze(test, 17, 42)
    event = test.signals.events[0]["evaluation"]
    original = test.pipeline.accepted_evidence.last_accepted.to_dict()
    test.indicators.value = IndicatorSnapshot(
        EmaSnapshot(1, 2, 0), RsiSnapshot(99), StochasticSnapshot(1, 2, 3, 4)
    )
    assert test.pipeline.accepted_evidence.last_accepted.to_dict() == original
    assert event["indicators"]["rsi"]["value"] == 55.1234567890123
    assert event["frame_id"] == 42
    assert event["snapshot_id"] == BASE.isoformat()
    assert event["visual_provenance"]["origin"] == "current_frame_analysis"
    provenance = event["indicator_provenance"]
    assert provenance["cache"]["cached_key"]["started_at"] == BASE.isoformat()
    assert provenance["calculation_frame_id"] is None
    assert provenance["calculated_at"] is None


def test_acceptance_without_entry_price_is_recorded_without_outcome():
    test = setup()
    enable(test)
    analyze(test, 2)
    event = test.signals.events[0]
    assert event["evaluation"]["price_evidence"]["reference"] is None
    assert event["executed_entry"] is False
    assert "outcome" not in event
    assert event["presentation_at"] is None


def test_signal_writer_failure_does_not_rollback_gate_and_retry_is_same_event():
    test = setup()
    enable(test)
    test.signals.fail = True
    with pytest.raises(OSError, match="signal write"):
        analyze(test, 2)
    evidence = test.pipeline.accepted_evidence.last_accepted
    assert not test.pipeline.accepted_evidence.last_accepted_persisted
    test.signals.fail = False
    test.pipeline.retry_accepted_evidence(evidence.acceptance_id)
    test.pipeline.retry_accepted_evidence(evidence.acceptance_id)
    assert test.pipeline.accepted_evidence.last_accepted_persisted
    assert test.signals.attempts[0][1] is test.signals.attempts[1][1]
    assert len(test.signals.events) == 1
    duplicate = analyze(test, 3)
    assert duplicate.is_duplicate_suppressed
    assert test.evaluator.calls == 2  # retries did not evaluate


def test_late_exit_is_linked_and_contains_no_result_or_carried_price():
    test = setup()
    enable(test)
    analyze(test, 2, 1)
    acceptance = test.pipeline.accepted_evidence.last_accepted
    analyze(test, 11, 2)
    assert test.observations.exits == []
    analyze(test, 13.5, 3)
    event = test.observations.exits[0]
    assert event["acceptance_id"] == acceptance.acceptance_id
    assert event["entry_evaluation_id"] == acceptance.evaluation.evaluation_id
    assert event["observed_at"] == at(13.5).isoformat()
    assert event["lateness_seconds"] == 1.5
    assert event["exit_evaluation"]["frame_id"] == 3
    assert event["exit_evaluation"]["price_evidence"]["reference"] is None
    assert "outcome" not in event
    assert "movement" not in event


def test_exit_retry_retains_first_due_frame_and_stable_id():
    test = setup()
    enable(test)
    analyze(test, 2)
    test.observations.fail = True
    with pytest.raises(OSError, match="exit write"):
        analyze(test, 13, 2)
    first = test.observations.exit_attempts[0]
    test.observations.fail = False
    analyze(test, 14, 3)
    assert test.observations.exit_attempts[1] is first
    assert test.observations.exits[0]["exit_evaluation"]["frame_id"] == 2


def test_no_exit_frame_does_not_fabricate_exit():
    test = setup()
    enable(test)
    analyze(test, 2)
    assert test.observations.exits == []
    assert test.pipeline.accepted_evidence.last_exit is None


def test_evaluations_share_snapshot_but_not_identity_and_restarts_differ():
    test = setup()
    enable(test)
    analyze(test, 2)
    first = test.pipeline.accepted_evidence.last_accepted
    analyze(test, 3)
    recorder = test.pipeline.accepted_evidence
    next_evaluation = recorder.capture(at(4), {})
    assert next_evaluation.evaluation_id != first.evaluation.evaluation_id
    assert recorder.execution_id != AcceptedSignalEvidenceRecorder().execution_id


def test_jsonl_signal_and_evidence_are_one_line_and_legacy_is_readable(tmp_path):
    path = tmp_path / "signals.jsonl"
    test = setup(signal_writer=JsonlSignalRecordWriter(path))
    analyze(test, 2)
    enable(test)
    analyze(test, 17, 2)
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    assert SignalRecordSerializer.read_accepted_evidence(rows[0]) is None
    evidence = SignalRecordSerializer.read_accepted_evidence(rows[1])
    assert evidence["evaluation"]["audit"]["call"]["passed_count"] == 7
    assert rows[1]["direction"] == "call"
    assert rows[1]["storage_format"] == "full"
    assert "write_started_at" in evidence
    assert (
        SignalRecordSerializer.read_accepted_evidence({"event_type": "other"}) is None
    )
    with pytest.raises(ValueError, match="Unsupported"):
        SignalRecordSerializer.read_accepted_evidence(
            {"accepted_evidence": {"version": 2}}
        )


def test_exit_jsonl_is_additive_without_outcome(tmp_path):
    path = tmp_path / "observations.jsonl"
    test = setup(strategy_writer=JsonlStrategyObservationWriter(path))
    enable(test)
    analyze(test, 2)
    analyze(test, 13, 2)
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    exit_event = next(
        r for r in rows if r["event_type"] == "accepted_signal_exit_evidence"
    )
    assert "outcome" not in exit_event
    assert "write_started_at" in exit_event


def test_rotation_and_duplicate_summaries_preserve_accepted_envelopes(tmp_path):
    path = tmp_path / "signals.jsonl"
    test = setup(
        signal_writer=JsonlSignalRecordWriter(path, max_bytes=500, backup_count=20)
    )
    enable(test)
    for second in (2, 3, 32, 33, 62, 63):
        analyze(test, second)
    rows = [
        json.loads(line)
        for p in tmp_path.glob("signals.jsonl*")
        for line in p.read_text(encoding="utf-8").splitlines()
    ]
    accepted = [r for r in rows if "accepted_evidence" in r]
    assert len(accepted) == 3
    assert len({r["accepted_evidence"]["acceptance_id"] for r in accepted}) == 3
    assert sum(r.get("event_type") == "duplicate_signal_summary" for r in rows) == 3


def test_unknown_objects_are_not_silently_serialized_as_missing():
    with pytest.raises(TypeError, match="Unsupported evidence"):
        json_snapshot({"unexpected": object()})


@pytest.mark.parametrize("direction", ["call", "put"])
@pytest.mark.parametrize("rsi", [10.0, 40.0, 55.0, 90.0])
def test_strict_and_gate_decisions_match_unmodified_evaluator(direction, rsi):
    test = setup(direction)
    enable(test)
    value = test.indicators.value
    test.indicators.value = IndicatorSnapshot(
        value.ema, RsiSnapshot(rsi), value.stochastic
    )
    expected = StrategyConditionEvaluator().evaluate(
        StrategyProfile.otc_precision_10s(),
        test.indicators.value,
        test.market.analyze(),
    )
    baseline_gate = ActionableSignalGate()
    for second in (2, 3, 32):
        record = analyze(test, second)
        assert record.signal.direction is expected.direction
        assert (
            record.disposition
            is baseline_gate.evaluate(expected, at(second)).disposition
        )
    assert test.evaluator.calls == test.indicators.calls == 3


def test_exit_is_never_linked_to_another_source_or_session():
    test = setup()
    enable(test)
    analyze(test, 2)
    test.pipeline.analyze_and_record(
        IMAGE,
        created_at=at(13),
        frame_id=2,
        monotonic_timestamp=13.0,
        source_key="other-source",
        session_key="other-session",
    )
    assert test.observations.exits == []
    analyze(test, 14, 3)
    assert test.observations.exits[0]["exit_evaluation"]["frame_id"] == 3


def test_memory_only_mode_does_not_claim_persistence():
    test = setup()
    test.pipeline._record_writer = None
    enable(test)
    analyze(test, 2)
    assert test.pipeline.accepted_evidence.last_accepted is not None
    assert not test.pipeline.accepted_evidence.last_accepted_persisted
    analyze(test, 13)
    assert test.pipeline.accepted_evidence.last_exit is not None
    assert test.observations.exits == []


def test_tampered_signal_cannot_borrow_another_acceptance(tmp_path):
    path = tmp_path / "signals.jsonl"
    test = setup(signal_writer=JsonlSignalRecordWriter(path))
    enable(test)
    analyze(test, 2)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["direction"] = "put"
    with pytest.raises(ValueError, match="does not match"):
        SignalRecordSerializer.read_accepted_evidence(payload)


def test_naive_timestamp_is_preserved_but_not_used_for_an_exit():
    from pocket_option_analyzer.domain.signals import (
        MarketSignal,
        SignalRecord,
        SignalStrength,
    )

    recorder = AcceptedSignalEvidenceRecorder()
    naive = BASE.replace(tzinfo=None)
    evaluation = recorder.capture(naive, {"observed_at": naive.isoformat()})
    record = SignalRecord(
        MarketSignal(SignalDirection.CALL, SignalStrength.HIGH, "fixture"),
        naive,
        disposition=SignalRecordDisposition.ACTIONABLE_ACCEPTED,
        candle_interval_started_at=naive,
    )
    recorder.accept(evaluation, record, BASE, memory_only=True)
    recorder.observe_exits(recorder.capture(naive + timedelta(seconds=11), {}))
    assert recorder.last_accepted.evaluation.observed_at.tzinfo is None
    assert recorder.last_exit is None


def test_acceptance_retry_after_duplicate_keeps_one_editable_summary(
    tmp_path, monkeypatch
):
    path = tmp_path / "signals.jsonl"
    writer = JsonlSignalRecordWriter(path)
    test = setup(signal_writer=writer)
    enable(test)
    append = writer._append_data

    def fail(data):
        raise OSError("fixture write failure")

    monkeypatch.setattr(writer, "_append_data", fail)
    with pytest.raises(OSError):
        analyze(test, 2)
    evidence = test.pipeline.accepted_evidence.last_accepted
    monkeypatch.setattr(writer, "_append_data", append)
    assert analyze(test, 3).is_duplicate_suppressed
    test.pipeline.retry_accepted_evidence(evidence.acceptance_id)
    assert analyze(test, 4).is_duplicate_suppressed
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    assert rows[0]["accepted_evidence"]["acceptance_id"] == evidence.acceptance_id
    assert rows[1]["event_type"] == "duplicate_signal_summary"
    assert rows[1]["duplicate_suppressed_count"] == 2
