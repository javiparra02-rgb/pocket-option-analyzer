from __future__ import annotations

from datetime import datetime

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
