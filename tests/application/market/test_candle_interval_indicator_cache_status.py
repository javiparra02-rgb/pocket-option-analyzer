from __future__ import annotations

from datetime import datetime

import pytest

from pocket_option_analyzer.application.market import (
    CandleIntervalIndicatorCacheStatus,
)
from pocket_option_analyzer.application.timing import (
    CandleIntervalKey,
)


def _key(
    second: int,
) -> CandleIntervalKey:

    return CandleIntervalKey(
        started_at=datetime(
            2026,
            7,
            31,
            11,
            9,
            second,
        ),
        duration_seconds=30,
    )


def test_cache_status_allows_signals_when_snapshot_is_current() -> None:

    current_key = _key(
        second=30,
    )

    status = CandleIntervalIndicatorCacheStatus(
        requested_key=current_key,
        cached_key=current_key,
        has_snapshot=True,
        is_current=True,
        is_settling=False,
    )

    assert status.state_label == "ACTUAL"
    assert status.allows_actionable_signals is True


def test_cache_status_rejects_current_state_from_another_interval() -> None:

    with pytest.raises(
        ValueError,
        match=("debe pertenecer al intervalo solicitado"),
    ):
        CandleIntervalIndicatorCacheStatus(
            requested_key=_key(
                second=30,
            ),
            cached_key=_key(
                second=0,
            ),
            has_snapshot=True,
            is_current=True,
            is_settling=False,
        )
