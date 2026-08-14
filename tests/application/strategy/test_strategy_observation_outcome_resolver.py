from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from pocket_option_analyzer.application.strategy import (
    StrategyObservationOutcome,
    StrategyObservationOutcomeResolver,
    VisualPriceReference,
)
from pocket_option_analyzer.domain.signals import SignalDirection

_ANCHORS = (
    ("bullish", 1.0, 0.8, 0.6, 0.4),
    ("bearish", 0.7, 0.5, 0.3, 0.0),
)


def _reference(value: float) -> VisualPriceReference:
    return VisualPriceReference(value, anchor_shape=_ANCHORS)


@pytest.mark.parametrize(
    ("direction", "exit_value", "expected"),
    (
        (SignalDirection.CALL, 101.0, StrategyObservationOutcome.WIN),
        (SignalDirection.CALL, 99.0, StrategyObservationOutcome.LOSS),
        (SignalDirection.CALL, 100.0, StrategyObservationOutcome.DRAW),
        (SignalDirection.PUT, 99.0, StrategyObservationOutcome.WIN),
        (SignalDirection.PUT, 101.0, StrategyObservationOutcome.LOSS),
        (SignalDirection.PUT, 100.0, StrategyObservationOutcome.DRAW),
    ),
)
def test_compare_call_and_put_outcomes(direction, exit_value, expected) -> None:
    assert StrategyObservationOutcomeResolver.compare(
        direction,
        _reference(100.0),
        _reference(exit_value),
    ) is expected


def test_compare_is_unresolved_without_reliable_reference() -> None:
    assert StrategyObservationOutcomeResolver.compare(
        SignalDirection.CALL, _reference(100.0), None,
    ) is StrategyObservationOutcome.UNRESOLVED


def test_resolver_uses_first_snapshot_at_or_after_resolve_at() -> None:
    instant = datetime(2026, 8, 9, tzinfo=UTC)
    observation = SimpleNamespace(
        observed_at=instant,
        resolve_at=instant + timedelta(seconds=10),
        candle_interval_started_at=instant,
        direction=SignalDirection.PUT,
        entry_reference=_reference(100.0),
    )
    resolver = StrategyObservationOutcomeResolver()
    assert resolver.add(observation) is True
    assert resolver.add(observation) is False
    assert resolver.resolve_due(
        instant + timedelta(seconds=9), _reference(90.0),
    ) == ()

    resolutions = resolver.resolve_due(
        instant + timedelta(seconds=10), _reference(90.0),
    )

    assert len(resolutions) == 1
    assert resolutions[0].resolved_at == instant + timedelta(seconds=10)
    assert resolutions[0].outcome is StrategyObservationOutcome.WIN
    assert resolutions[0].entry_visual_price_context is None
    assert resolutions[0].exit_visual_price_context is None
    assert resolver.resolve_due(
        instant + timedelta(seconds=11), _reference(80.0),
    ) == ()


def test_due_observation_without_exit_is_resolved_as_unresolved() -> None:
    instant = datetime(2026, 8, 9, tzinfo=UTC)
    observation = SimpleNamespace(
        observed_at=instant,
        resolve_at=instant + timedelta(seconds=10),
        candle_interval_started_at=instant,
        direction=SignalDirection.CALL,
        entry_reference=_reference(100.0),
    )
    resolver = StrategyObservationOutcomeResolver()
    resolver.add(observation)

    resolution = resolver.resolve_due(instant + timedelta(seconds=10), None)[0]

    assert resolution.exit_reference is None
    assert resolution.outcome is StrategyObservationOutcome.UNRESOLVED


def test_compare_is_unresolved_when_anchor_frames_are_not_comparable() -> None:
    changed = VisualPriceReference(
        0.6,
        anchor_shape=(("bullish", 1.0, 0.7, 0.5, 0.1),),
    )

    assert StrategyObservationOutcomeResolver.compare(
        SignalDirection.CALL,
        _reference(0.5),
        changed,
    ) is StrategyObservationOutcome.UNRESOLVED


def test_resolver_rejects_naive_timestamps() -> None:
    resolver = StrategyObservationOutcomeResolver()
    observation = SimpleNamespace(
        observed_at=datetime(2026, 8, 9),
        resolve_at=datetime(2026, 8, 9, 0, 0, 10),
        candle_interval_started_at=datetime(2026, 8, 9),
        direction=SignalDirection.CALL,
        entry_reference=_reference(0.5),
    )
    resolver.add(observation)

    with pytest.raises(ValueError, match="zona horaria"):
        resolver.resolve_due(datetime(2026, 8, 9, 0, 0, 11), _reference(0.6))
