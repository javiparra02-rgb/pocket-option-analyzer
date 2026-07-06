from pocket_option_analyzer.domain.indicators import (
    EmaSnapshot,
    IndicatorSnapshot,
    RsiSnapshot,
    StochasticSnapshot,
)


def test_indicator_snapshot_groups_indicator_states() -> None:

    snapshot = IndicatorSnapshot(
        ema=EmaSnapshot(
            fast_value=105.0,
            slow_value=100.0,
            separation_candles=3,
        ),
        rsi=RsiSnapshot(
            value=57.0,
        ),
        stochastic=StochasticSnapshot(
            k_previous=18.0,
            d_previous=20.0,
            k_value=24.0,
            d_value=21.0,
        ),
    )

    assert snapshot.ema.is_bullish_alignment is True
    assert snapshot.rsi.is_between(52.0, 65.0) is True
    assert snapshot.stochastic.crossed_up is True