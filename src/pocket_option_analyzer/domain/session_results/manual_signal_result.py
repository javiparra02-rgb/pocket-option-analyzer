from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import uuid4

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


class ManualSignalResultEventType(str, Enum):
    """
    Tipo de evento almacenado en el historial auditable.
    """

    RECORDED = "RECORDED"
    REVERSED = "REVERSED"


def _new_event_id() -> str:
    return uuid4().hex


@dataclass(frozen=True, slots=True)
class ManualSignalResultRecord:
    """
    Evento auditable asociado al resultado manual de una señal.

    RECORDED:
        Registra una ganancia o pérdida.

    REVERSED:
        Revierte un evento RECORDED anterior sin eliminarlo
        físicamente del archivo JSONL.
    """

    signal_created_at: datetime
    direction: SignalDirection
    strength: SignalStrength
    result: ManualSignalResult
    registered_at: datetime
    source: str
    reason: str = ""
    strategy_name: str = "OTC_PRECISION_10S"
    event_id: str = field(
        default_factory=_new_event_id,
    )
    event_type: ManualSignalResultEventType = ManualSignalResultEventType.RECORDED
    reverses_event_id: str | None = None

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
            raise ValueError("source no puede estar vacío.")

        if not self.strategy_name.strip():
            raise ValueError("strategy_name no puede estar vacío.")

        if not self.event_id.strip():
            raise ValueError("event_id no puede estar vacío.")

        if self.event_type == ManualSignalResultEventType.REVERSED and not (
            self.reverses_event_id and self.reverses_event_id.strip()
        ):
            raise ValueError("Un evento REVERSED debe indicar reverses_event_id.")

        if (
            self.event_type == ManualSignalResultEventType.RECORDED
            and self.reverses_event_id is not None
        ):
            raise ValueError("Un evento RECORDED no puede indicar reverses_event_id.")

    @staticmethod
    def _validate_aware_datetime(
        value: datetime,
        field_name: str,
    ) -> None:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{field_name} debe incluir zona horaria.")
