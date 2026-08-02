from pocket_option_analyzer.domain.strategy import StrategyProfile


def test_otc_precision_profile_contains_time_settings() -> None:

    profile = StrategyProfile.otc_precision_10s()

    assert profile.name == "OTC Precision 10S"
    assert profile.candle_seconds == 30
    assert profile.expiration_seconds == 10


def test_otc_precision_profile_contains_indicator_settings() -> None:

    profile = StrategyProfile.otc_precision_10s()

    assert profile.ema_fast_period == 5
    assert profile.ema_slow_period == 13
    assert profile.ema_min_separation_candles == 3

    assert profile.rsi_period == 7
    assert profile.rsi_midline == 50.0
    assert profile.rsi_call_min == 52.0
    assert profile.rsi_call_max == 65.0
    assert profile.rsi_put_min == 35.0
    assert profile.rsi_put_max == 48.0

    assert profile.stoch_k_period == 5
    assert profile.stoch_d_period == 3
    assert profile.stoch_smooth_period == 3
    assert profile.stoch_oversold_level == 20.0
    assert profile.stoch_overbought_level == 80.0
    assert profile.stoch_call_trigger_max == 30.0
    assert profile.stoch_put_trigger_min == 70.0


def test_otc_precision_profile_contains_candle_filters() -> None:

    profile = StrategyProfile.otc_precision_10s()

    assert profile.signal_body_ratio_min == 0.60
    assert profile.spike_wick_body_ratio == 2.0


def test_otc_precision_profile_contains_risk_settings() -> None:

    profile = StrategyProfile.otc_precision_10s()

    assert profile.risk_per_operation_min_pct == 1.0
    assert profile.risk_per_operation_max_pct == 2.0
    assert profile.max_consecutive_losses == 3
    assert profile.daily_loss_limit_pct == 5.0
    assert profile.daily_target_min_pct == 3.0
    assert profile.daily_target_max_pct == 5.0
    assert profile.rest_interval_minutes == 30
    assert profile.max_operations_per_hour == 12
