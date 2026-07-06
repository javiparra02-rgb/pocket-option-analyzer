from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StrategyProfile:
    """
    Configuración declarativa de una estrategia.

    Esta clase no genera señales por sí misma.
    Solo define los parámetros que usará el motor de estrategia.
    """

    name: str

    candle_seconds: int

    expiration_seconds: int

    ema_fast_period: int

    ema_slow_period: int

    ema_min_separation_candles: int

    rsi_period: int

    rsi_midline: float

    rsi_call_min: float

    rsi_call_max: float

    rsi_put_min: float

    rsi_put_max: float

    stoch_k_period: int

    stoch_d_period: int

    stoch_smooth_period: int

    stoch_oversold_level: float

    stoch_overbought_level: float

    stoch_call_trigger_max: float

    stoch_put_trigger_min: float

    signal_body_ratio_min: float

    spike_wick_body_ratio: float

    risk_per_operation_min_pct: float

    risk_per_operation_max_pct: float

    max_consecutive_losses: int

    daily_loss_limit_pct: float

    daily_target_min_pct: float

    daily_target_max_pct: float

    rest_interval_minutes: int

    max_operations_per_hour: int

    @classmethod
    def otc_precision_10s(cls) -> StrategyProfile:
        """
        Perfil oficial OTC Precision 10S para Pocket Option.

        Basado en:
        - velas de 30 segundos
        - expiración de 10 segundos
        - EMA 5 / EMA 13
        - RSI(7)
        - Stoch(5,3,3)
        """

        return cls(
            name="OTC Precision 10S",
            candle_seconds=30,
            expiration_seconds=10,
            ema_fast_period=5,
            ema_slow_period=13,
            ema_min_separation_candles=3,
            rsi_period=7,
            rsi_midline=50.0,
            rsi_call_min=52.0,
            rsi_call_max=65.0,
            rsi_put_min=35.0,
            rsi_put_max=48.0,
            stoch_k_period=5,
            stoch_d_period=3,
            stoch_smooth_period=3,
            stoch_oversold_level=20.0,
            stoch_overbought_level=80.0,
            stoch_call_trigger_max=30.0,
            stoch_put_trigger_min=70.0,
            signal_body_ratio_min=0.60,
            spike_wick_body_ratio=2.0,
            risk_per_operation_min_pct=1.0,
            risk_per_operation_max_pct=2.0,
            max_consecutive_losses=3,
            daily_loss_limit_pct=5.0,
            daily_target_min_pct=3.0,
            daily_target_max_pct=5.0,
            rest_interval_minutes=30,
            max_operations_per_hour=12,
        )