from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from pocket_option_analyzer.application.timing import (
    CandleIntervalResolver,
)


def test_resolver_aligns_first_half_minute_to_second_zero() -> None:

    resolver = CandleIntervalResolver(
        duration_seconds=30,
    )

    result = resolver.resolve(
        observed_at=datetime(
            2026,
            7,
            30,
            16,
            44,
            17,
            500000,
        ),
    )

    assert result.started_at == datetime(
        2026,
        7,
        30,
        16,
        44,
        0,
    )
    assert result.duration_seconds == 30


def test_resolver_aligns_second_half_minute_to_second_thirty() -> None:

    resolver = CandleIntervalResolver(
        duration_seconds=30,
    )

    result = resolver.resolve(
        observed_at=datetime(
            2026,
            7,
            30,
            16,
            44,
            58,
        ),
    )

    assert result.started_at == datetime(
        2026,
        7,
        30,
        16,
        44,
        30,
    )


def test_resolver_preserves_timezone() -> None:

    chile_timezone = timezone(
        timedelta(
            hours=-4,
        )
    )

    observed_at = datetime(
        2026,
        7,
        30,
        16,
        44,
        35,
        tzinfo=chile_timezone,
    )

    result = CandleIntervalResolver().resolve(
        observed_at=observed_at,
    )

    assert result.started_at.tzinfo is chile_timezone
    assert result.contains(
        datetime(
            2026,
            7,
            30,
            16,
            44,
            59,
            tzinfo=chile_timezone,
        )
    ) is True


def test_resolver_rejects_duration_that_does_not_divide_minute() -> None:

    with pytest.raises(
        ValueError,
        match="debe dividir exactamente un minuto",
    ):
        CandleIntervalResolver(
            duration_seconds=17,
        )