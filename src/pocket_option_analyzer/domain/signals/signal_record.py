from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .market_signal import MarketSignal


@dataclass(frozen=True, slots=True)
class SignalRecord:
    """
    Registro histórico de una señal generada por el sistema.

    No representa una operación ejecutada.
    Solo registra una señal informativa.
    """

    signal: MarketSignal

    created_at: datetime

    source: str = "signal_analysis"

    @property
    def is_actionable(self) -> bool:
        """
        Indica si la señal registrada era accionable.
        """

        return self.signal.is_actionable