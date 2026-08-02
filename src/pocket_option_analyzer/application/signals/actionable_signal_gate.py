from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pocket_option_analyzer.application.timing import (
    CandleIntervalKey,
    CandleIntervalResolver,
)
from pocket_option_analyzer.domain.signals import (
    MarketSignal,
    SignalRecordDisposition,
)


@dataclass(
    frozen=True,
    slots=True,
)
class ActionableSignalGateDecision:
    """
    Decisión tomada para una señal dentro de una vela temporal.
    """

    disposition: SignalRecordDisposition
    interval_key: CandleIntervalKey

    @property
    def is_duplicate_suppressed(
        self,
    ) -> bool:
        return self.disposition is SignalRecordDisposition.DUPLICATE_SUPPRESSED


class ActionableSignalGate:
    """
    Admite como máximo una señal CALL o PUT por vela.

    Las señales neutrales no reservan el intervalo.

    Cuando una señal accionable ya fue aceptada, cualquier CALL o PUT
    posterior dentro de la misma clave queda suprimida, incluso si
    cambia la dirección.
    """

    def __init__(
        self,
        interval_resolver: CandleIntervalResolver | None = None,
    ) -> None:
        self._interval_resolver = interval_resolver or CandleIntervalResolver(
            duration_seconds=30,
        )

        self._accepted_intervals: set[CandleIntervalKey] = set()

    @property
    def accepted_interval_count(
        self,
    ) -> int:
        return len(
            self._accepted_intervals,
        )

    def evaluate(
        self,
        signal: MarketSignal,
        observed_at: datetime,
    ) -> ActionableSignalGateDecision:
        """
        Clasifica la señal dentro de su intervalo temporal.
        """

        interval_key = self._interval_resolver.resolve(
            observed_at=observed_at,
        )

        if not signal.is_actionable:
            return ActionableSignalGateDecision(
                disposition=SignalRecordDisposition.OBSERVED,
                interval_key=interval_key,
            )

        if interval_key in self._accepted_intervals:
            return ActionableSignalGateDecision(
                disposition=(SignalRecordDisposition.DUPLICATE_SUPPRESSED),
                interval_key=interval_key,
            )

        self._accepted_intervals.add(
            interval_key,
        )

        return ActionableSignalGateDecision(
            disposition=(SignalRecordDisposition.ACTIONABLE_ACCEPTED),
            interval_key=interval_key,
        )

    def reset(
        self,
    ) -> None:
        """
        Limpia las claves almacenadas.

        Se utiliza principalmente en pruebas o al reiniciar completamente
        el motor, no al reiniciar solamente el contador visual.
        """

        self._accepted_intervals.clear()
