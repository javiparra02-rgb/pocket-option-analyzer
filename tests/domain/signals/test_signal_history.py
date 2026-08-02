from datetime import UTC, datetime

import pytest

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


def test_signal_history_keeps_only_most_recent_records() -> None:

    first = _record(
        SignalDirection.CALL,
    )

    second = _record(
        SignalDirection.NONE,
    )

    third = _record(
        SignalDirection.PUT,
    )

    history = SignalHistory(
        max_records=2,
    )

    history.append(
        first,
    )

    history.append(
        second,
    )

    history.append(
        third,
    )

    assert history.records == [
        second,
        third,
    ]

    assert len(history) == 2
    assert history.is_full is True
    assert history.latest() is third


def test_signal_history_trims_initial_records_to_capacity() -> None:

    first = _record(
        SignalDirection.CALL,
    )

    second = _record(
        SignalDirection.NONE,
    )

    third = _record(
        SignalDirection.PUT,
    )

    history = SignalHistory(
        records=[
            first,
            second,
            third,
        ],
        max_records=2,
    )

    assert history.records == [
        second,
        third,
    ]

    assert history.latest() is third


@pytest.mark.parametrize(
    "max_records",
    [
        0,
        -1,
    ],
)
def test_signal_history_rejects_invalid_capacity(
    max_records: int,
) -> None:

    with pytest.raises(
        ValueError,
        match="mayor o igual a 1",
    ):
        SignalHistory(
            max_records=max_records,
        )
