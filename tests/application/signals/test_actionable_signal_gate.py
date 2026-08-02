from __future__ import annotations

from datetime import datetime, timedelta

from pocket_option_analyzer.application.signals import (
    ActionableSignalGate,
)
from pocket_option_analyzer.domain.signals import (
    MarketSignal,
    SignalDirection,
    SignalRecordDisposition,
    SignalStrength,
)


def _signal(
    direction: SignalDirection,
) -> MarketSignal:

    return MarketSignal(
        direction=direction,
        strength=(
            SignalStrength.NONE
            if direction is SignalDirection.NONE
            else SignalStrength.HIGH
        ),
        reason="Test signal.",
    )


def test_gate_accepts_first_actionable_signal() -> None:

    gate = ActionableSignalGate()

    decision = gate.evaluate(
        signal=_signal(
            SignalDirection.CALL,
        ),
        observed_at=datetime(
            2026,
            7,
            31,
            10,
            30,
            8,
        ),
    )

    assert decision.disposition is SignalRecordDisposition.ACTIONABLE_ACCEPTED
    assert decision.interval_key.started_at.second == 0


def test_gate_suppresses_any_second_direction_in_same_candle() -> None:

    gate = ActionableSignalGate()

    gate.evaluate(
        signal=_signal(
            SignalDirection.CALL,
        ),
        observed_at=datetime(
            2026,
            7,
            31,
            10,
            30,
            8,
        ),
    )

    duplicate = gate.evaluate(
        signal=_signal(
            SignalDirection.PUT,
        ),
        observed_at=datetime(
            2026,
            7,
            31,
            10,
            30,
            20,
        ),
    )

    assert duplicate.disposition is SignalRecordDisposition.DUPLICATE_SUPPRESSED


def test_gate_accepts_signal_in_next_candle() -> None:

    gate = ActionableSignalGate()

    first = gate.evaluate(
        signal=_signal(
            SignalDirection.CALL,
        ),
        observed_at=datetime(
            2026,
            7,
            31,
            10,
            30,
            20,
        ),
    )

    second = gate.evaluate(
        signal=_signal(
            SignalDirection.CALL,
        ),
        observed_at=datetime(
            2026,
            7,
            31,
            10,
            30,
            35,
        ),
    )

    assert first.disposition is SignalRecordDisposition.ACTIONABLE_ACCEPTED
    assert second.disposition is SignalRecordDisposition.ACTIONABLE_ACCEPTED
    assert first.interval_key != second.interval_key
    assert gate.accepted_interval_count == 1

    assert gate.accepted_interval_key == second.interval_key


def test_neutral_signal_does_not_reserve_candle() -> None:

    gate = ActionableSignalGate()

    neutral = gate.evaluate(
        signal=_signal(
            SignalDirection.NONE,
        ),
        observed_at=datetime(
            2026,
            7,
            31,
            10,
            30,
            5,
        ),
    )

    actionable = gate.evaluate(
        signal=_signal(
            SignalDirection.PUT,
        ),
        observed_at=datetime(
            2026,
            7,
            31,
            10,
            30,
            15,
        ),
    )

    assert neutral.disposition is SignalRecordDisposition.OBSERVED
    assert actionable.disposition is SignalRecordDisposition.ACTIONABLE_ACCEPTED


def test_gate_keeps_only_latest_interval_during_long_session() -> None:

    gate = ActionableSignalGate()

    session_started_at = datetime(
        2026,
        8,
        1,
        10,
        0,
        0,
    )

    last_decision = None

    for interval_index in range(
        1000,
    ):
        observed_at = session_started_at + timedelta(
            seconds=(interval_index * 30 + 5),
        )

        last_decision = gate.evaluate(
            signal=_signal(
                SignalDirection.CALL,
            ),
            observed_at=observed_at,
        )

        assert last_decision.disposition is SignalRecordDisposition.ACTIONABLE_ACCEPTED

        assert gate.accepted_interval_count == 1

    assert last_decision is not None

    assert gate.accepted_interval_key == last_decision.interval_key


def test_gate_reset_releases_accepted_interval() -> None:

    gate = ActionableSignalGate()

    gate.evaluate(
        signal=_signal(
            SignalDirection.PUT,
        ),
        observed_at=datetime(
            2026,
            8,
            1,
            10,
            30,
            5,
        ),
    )

    assert gate.accepted_interval_count == 1
    assert gate.accepted_interval_key is not None

    gate.reset()

    assert gate.accepted_interval_count == 0
    assert gate.accepted_interval_key is None

    decision = gate.evaluate(
        signal=_signal(
            SignalDirection.PUT,
        ),
        observed_at=datetime(
            2026,
            8,
            1,
            10,
            30,
            10,
        ),
    )

    assert decision.disposition is SignalRecordDisposition.ACTIONABLE_ACCEPTED
