from __future__ import annotations

from datetime import datetime, timedelta

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


def test_cache_reports_settling_status_for_previous_snapshot() -> None:

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
            31,
            11,
            9,
            20,
        ),
        snapshot_factory=lambda: first_snapshot,
    )

    result = cache.resolve(
        observed_at=datetime(
            2026,
            7,
            31,
            11,
            9,
            30,
            500000,
        ),
        snapshot_factory=lambda: _snapshot(
            value=70.0,
        ),
    )

    status = cache.last_status

    assert result is first_snapshot
    assert status is not None
    assert status.state_label == "ESTABILIZANDO"
    assert status.is_current is False
    assert status.allows_actionable_signals is False
    assert status.requested_key.started_at.second == 30
    assert status.cached_key is not None
    assert status.cached_key.started_at.second == 0


def test_cache_keeps_only_latest_snapshot_during_long_session() -> None:

    cache = CandleIntervalIndicatorCache(
        settling_seconds=0.0,
    )

    session_started_at = datetime(
        2026,
        7,
        30,
        16,
        44,
        0,
    )

    latest_snapshot: IndicatorSnapshot | None = None
    latest_observed_at = session_started_at

    for interval_index in range(
        1_000,
    ):
        latest_observed_at = session_started_at + timedelta(
            seconds=interval_index * 30,
        )

        candidate_snapshot = _snapshot(
            value=50.0 + interval_index % 10,
        )

        result = cache.resolve(
            observed_at=latest_observed_at,
            snapshot_factory=(
                lambda candidate_snapshot=candidate_snapshot: candidate_snapshot
            ),
        )

        assert result is candidate_snapshot
        assert cache.cached_snapshot is candidate_snapshot

        latest_snapshot = candidate_snapshot

    assert cache.cached_snapshot is latest_snapshot

    assert cache.cached_key is not None

    assert cache.cached_key.started_at == latest_observed_at

    assert cache.last_status is not None
    assert cache.last_status.is_current is True
    assert cache.last_status.allows_actionable_signals is True


def test_cache_reset_clears_state_and_allows_reuse() -> None:

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

    assert cache.cached_key is not None
    assert cache.cached_snapshot is first_snapshot
    assert cache.last_status is not None

    cache.reset()

    assert cache.cached_key is None
    assert cache.cached_snapshot is None
    assert cache.last_status is None

    second_snapshot = _snapshot(
        value=70.0,
    )

    result = cache.resolve(
        observed_at=datetime(
            2026,
            7,
            30,
            16,
            45,
            10,
        ),
        snapshot_factory=lambda: second_snapshot,
    )

    assert result is second_snapshot
    assert cache.cached_snapshot is second_snapshot
    assert cache.cached_key is not None
    assert cache.last_status is not None
    assert cache.last_status.is_current is True
