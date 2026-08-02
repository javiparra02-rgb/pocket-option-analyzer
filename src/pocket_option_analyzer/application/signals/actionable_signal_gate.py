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

    Solo conserva la última clave que aceptó una señal, por lo que
    su consumo de memoria permanece constante durante toda la ejecución.
    """

    def __init__(
        self,
        interval_resolver: CandleIntervalResolver | None = None,
    ) -> None:
        self._interval_resolver = interval_resolver or CandleIntervalResolver(
            duration_seconds=30,
        )

        self._accepted_interval_key: CandleIntervalKey | None = None

    @property
    def accepted_interval_key(
        self,
    ) -> CandleIntervalKey | None:
        """
        Último intervalo en el que se aceptó una señal accionable.
        """

        return self._accepted_interval_key

    @property
    def accepted_interval_count(
        self,
    ) -> int:
        """
        Cantidad de claves mantenidas actualmente en memoria.

        El resultado siempre será cero o uno.
        """

        return int(self._accepted_interval_key is not None)

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
                disposition=(SignalRecordDisposition.OBSERVED),
                interval_key=interval_key,
            )

        if interval_key == self._accepted_interval_key:
            return ActionableSignalGateDecision(
                disposition=(SignalRecordDisposition.DUPLICATE_SUPPRESSED),
                interval_key=interval_key,
            )

        self._accepted_interval_key = interval_key

        return ActionableSignalGateDecision(
            disposition=(SignalRecordDisposition.ACTIONABLE_ACCEPTED),
            interval_key=interval_key,
        )

    def reset(
        self,
    ) -> None:
        """
        Libera la clave actualmente almacenada.

        Se utiliza al reiniciar completamente el motor, no al reiniciar
        únicamente los contadores visuales de la sesión.
        """

        self._accepted_interval_key = None
