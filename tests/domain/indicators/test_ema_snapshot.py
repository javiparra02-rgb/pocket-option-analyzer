from pocket_option_analyzer.domain.indicators import EmaSnapshot


def test_ema_snapshot_detects_bullish_alignment() -> None:

    snapshot = EmaSnapshot(
        fast_value=105.0,
        slow_value=100.0,
        separation_candles=3,
    )

    assert snapshot.is_bullish_alignment is True
    assert snapshot.is_bearish_alignment is False


def test_ema_snapshot_detects_bearish_alignment() -> None:

    snapshot = EmaSnapshot(
        fast_value=95.0,
        slow_value=100.0,
        separation_candles=3,
    )

    assert snapshot.is_bullish_alignment is False
    assert snapshot.is_bearish_alignment is True
