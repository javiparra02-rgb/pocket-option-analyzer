from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from pocket_option_analyzer.domain.signals import (
    SignalDirection,
    SignalStrength,
)


class ManualSignalResult(str, Enum):
    """
    Resultado registrado manualmente para una señal confirmada.
    """

    WIN = "WIN"
    LOSS = "LOSS"


@dataclass(frozen=True, slots=True)
class ManualSignalResultRecord:
    """
    Registro auditable del resultado manual de una señal.

    No representa una operación ejecutada automáticamente.
    El resultado es proporcionado manualmente por el usuario.
    """

    signal_created_at: datetime
    direction: SignalDirection
    strength: SignalStrength
    result: ManualSignalResult
    registered_at: datetime
    source: str
    reason: str = ""
    strategy_name: str = "OTC_PRECISION_10S"

    def __post_init__(
        self,
    ) -> None:
        self._validate_aware_datetime(
            value=self.signal_created_at,
            field_name="signal_created_at",
        )
        self._validate_aware_datetime(
            value=self.registered_at,
            field_name="registered_at",
        )

        if not self.source.strip():
            raise ValueError(
                "source no puede estar vacío."
            )

        if not self.strategy_name.strip():
            raise ValueError(
                "strategy_name no puede estar vacío."
            )

    @staticmethod
    def _validate_aware_datetime(
        value: datetime,
        field_name: str,
    ) -> None:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                f"{field_name} debe incluir zona horaria."
            )