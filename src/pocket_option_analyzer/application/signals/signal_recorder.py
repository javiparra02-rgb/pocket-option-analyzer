from __future__ import annotations

from datetime import datetime, timezone

from pocket_option_analyzer.domain.signals import (
    MarketSignal,
    SignalHistory,
    SignalRecord,
    SignalRecordDisposition,
)


class SignalRecorder:
    """
    Registra señales generadas por el sistema en un historial en memoria.

    No ejecuta operaciones.
    No interactúa con Pocket Option.
    Solo guarda señales informativas.
    """

    def __init__(
        self,
        history: SignalHistory,
    ) -> None:
        self._history = history

    def record(
        self,
        signal: MarketSignal,
        created_at: datetime | None = None,
        source: str = "strategy_signal_analysis",
        disposition: SignalRecordDisposition = (
            SignalRecordDisposition.OBSERVED
        ),
        candle_interval_started_at: datetime | None = None,
    ) -> SignalRecord:
        """
        Crea un registro y lo agrega al historial.
        """

        record = SignalRecord(
            signal=signal,
            created_at=(
                created_at
                or datetime.now(
                    timezone.utc,
                )
            ),
            source=source,
            disposition=disposition,
            candle_interval_started_at=(
                candle_interval_started_at
            ),
        )

        self._history.append(
            record,
        )

        return record