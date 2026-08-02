from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .market_signal import MarketSignal
from .signal_record_disposition import SignalRecordDisposition


@dataclass(
    frozen=True,
    slots=True,
)
class SignalRecord:
    """
    Registro histórico de una señal generada por el sistema.

    No representa una operación ejecutada.
    Solo registra una señal informativa.
    """

    signal: MarketSignal

    created_at: datetime

    source: str = "signal_analysis"

    disposition: SignalRecordDisposition = SignalRecordDisposition.OBSERVED

    candle_interval_started_at: datetime | None = None

    def __post_init__(
        self,
    ) -> None:
        if (
            self.disposition is not SignalRecordDisposition.OBSERVED
            and self.candle_interval_started_at is None
        ):
            raise ValueError(
                "Las señales clasificadas por el gate deben "
                "incluir candle_interval_started_at."
            )

    @property
    def is_duplicate_suppressed(
        self,
    ) -> bool:
        return self.disposition is SignalRecordDisposition.DUPLICATE_SUPPRESSED

    @property
    def is_actionable(
        self,
    ) -> bool:
        """
        Solo una señal aceptada puede activar efectos operativos.

        Una duplicada conserva su dirección y diagnóstico para auditoría,
        pero deja de considerarse accionable.
        """

        return self.signal.is_actionable and not self.is_duplicate_suppressed
