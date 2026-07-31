from __future__ import annotations

from datetime import datetime

from pocket_option_analyzer.application.market import (
    CandleIntervalIndicatorCache,
)
from pocket_option_analyzer.domain.indicators import (
    EmaSnapshot,
    IndicatorSnapshot,
    RsiSnapshot,
    StochasticSnapshot,
)


def _snapshot(
    value: float,
) -> IndicatorSnapshot:

    return IndicatorSnapshot(
        ema=EmaSnapshot(
            fast_value=value,
            slow_value=value - 1.0,
            separation_candles=3,
        ),
        rsi=RsiSnapshot(
            value=value,
        ),
        stochastic=StochasticSnapshot(
            k_previous=value - 2.0,
            d_previous=value - 1.0,
            k_value=value,
            d_value=value - 0.5,
        ),
    )


def test_cache_builds_first_snapshot() -> None:

    cache = CandleIntervalIndicatorCache()
    snapshot = _snapshot(
        value=50.0,
    )
    calls = 0

    def factory() -> IndicatorSnapshot:
        nonlocal calls
        calls += 1
        return snapshot

    result = cache.resolve(
        observed_at=datetime(
            2026,
            7,
            30,
            16,
            44,
            10,
        ),
        snapshot_factory=factory,
    )

    assert result is snapshot
    assert calls == 1
    assert cache.cached_snapshot is snapshot
    assert cache.cached_key is not None
    assert cache.cached_key.started_at.second == 0


def test_cache_reuses_snapshot_inside_same_interval() -> None:

    cache = CandleIntervalIndicatorCache()
    first_snapshot = _snapshot(
        value=50.0,
    )

    cache.resolve(
        observed_at=datetime(
            2026,
            7,
            30,
            16,
            44,
            5,
        ),
        snapshot_factory=lambda: first_snapshot,
    )

    calls = 0

    def unexpected_factory() -> IndicatorSnapshot:
        nonlocal calls
        calls += 1
        return _snapshot(
            value=70.0,
        )

    result = cache.resolve(
        observed_at=datetime(
            2026,
            7,
            30,
            16,
            44,
            25,
        ),
        snapshot_factory=unexpected_factory,
    )

    assert result is first_snapshot
    assert calls == 0


def test_cache_preserves_previous_snapshot_during_settling_time() -> None:

    cache = CandleIntervalIndicatorCache(
        settling_seconds=2.0,
    )
    first_snapshot = _snapshot(
        value=50.0,
    )

    cache.resolve(
        observed_at=datetime(
            2026,
            7,
            30,
            16,
            44,
            20,
        ),
        snapshot_factory=lambda: first_snapshot,
    )

    calls = 0

    def unexpected_factory() -> IndicatorSnapshot:
        nonlocal calls
        calls += 1
        return _snapshot(
            value=70.0,
        )

    result = cache.resolve(
        observed_at=datetime(
            2026,
            7,
            30,
            16,
            44,
            30,
            500000,
        ),
        snapshot_factory=unexpected_factory,
    )

    assert result is first_snapshot
    assert calls == 0


def test_cache_calculates_new_snapshot_after_settling_time() -> None:

    cache = CandleIntervalIndicatorCache(
        settling_seconds=2.0,
    )
    first_snapshot = _snapshot(
        value=50.0,
    )
    second_snapshot = _snapshot(
        value=70.0,
    )

    cache.resolve(
        observed_at=datetime(
            2026,
            7,
            30,
            16,
            44,
            20,
        ),
        snapshot_factory=lambda: first_snapshot,
    )

    result = cache.resolve(
        observed_at=datetime(
            2026,
            7,
            30,
            16,
            44,
            32,
        ),
        snapshot_factory=lambda: second_snapshot,
    )

    assert result is second_snapshot
    assert cache.cached_snapshot is second_snapshot
    assert cache.cached_key is not None
    assert cache.cached_key.started_at.second == 30


def test_cache_preserves_last_valid_snapshot_when_new_build_fails() -> None:

    cache = CandleIntervalIndicatorCache()
    first_snapshot = _snapshot(
        value=50.0,
    )

    cache.resolve(
        observed_at=datetime(
            2026,
            7,
            30,
            16,
            44,
            10,
        ),
        snapshot_factory=lambda: first_snapshot,
    )

    result = cache.resolve(
        observed_at=datetime(
            2026,
            7,
            30,
            16,
            44,
            32,
        ),
        snapshot_factory=lambda: None,
    )

    assert result is first_snapshot