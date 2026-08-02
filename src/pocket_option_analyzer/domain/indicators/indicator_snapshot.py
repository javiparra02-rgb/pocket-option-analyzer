from __future__ import annotations

from dataclasses import dataclass

from .ema_snapshot import EmaSnapshot
from .rsi_snapshot import RsiSnapshot
from .stochastic_snapshot import StochasticSnapshot


@dataclass(frozen=True, slots=True)
class IndicatorSnapshot:
    """
    Agrupa el estado actual de los indicadores requeridos por la estrategia.
    """

    ema: EmaSnapshot

    rsi: RsiSnapshot

    stochastic: StochasticSnapshot
