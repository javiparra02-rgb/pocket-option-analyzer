from datetime import UTC, datetime

from pocket_option_analyzer.domain.signals import (
    MarketSignal,
    SignalDirection,
    SignalHistory,
    SignalRecord,
    SignalStrength,
)


def _record(
    direction: SignalDirection,
) -> SignalRecord:

    strength = (
        SignalStrength.MEDIUM
        if direction is not SignalDirection.NONE
        else SignalStrength.NONE
    )

    return SignalRecord(
        signal=MarketSignal(
            direction=direction,
            strength=strength,
            reason="Test signal.",
        ),
        created_at=datetime(
            2026,
            1,
            1,
            tzinfo=UTC,
        ),
    )


def test_signal_history_returns_latest_record() -> None:

    first = _record(SignalDirection.NONE)
    second = _record(SignalDirection.CALL)

    history = SignalHistory()

    history.append(first)
    history.append(second)

    assert history.latest() is second


def test_signal_history_filters_actionable_records() -> None:

    neutral = _record(SignalDirection.NONE)
    call = _record(SignalDirection.CALL)
    put = _record(SignalDirection.PUT)

    history = SignalHistory()

    history.append(neutral)
    history.append(call)
    history.append(put)

    actionable = history.actionable()

    assert actionable == [
        call,
        put,
    ]


def test_signal_history_can_be_cleared() -> None:

    history = SignalHistory()

    history.append(_record(SignalDirection.CALL))

    history.clear()

    assert history.latest() is None
    assert history.records == []
