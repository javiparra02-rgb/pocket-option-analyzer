from __future__ import annotations

from typing import Any

from pocket_option_analyzer.domain.signals import SignalRecord


class SignalRecordSerializer:
    """
    Convierte un SignalRecord en una estructura serializable.

    No escribe archivos.
    Solo transforma el registro a un diccionario compatible con JSON.
    """

    def to_dict(
        self,
        record: SignalRecord,
    ) -> dict[str, Any]:

        return {
            "created_at": record.created_at.isoformat(),
            "candle_interval_started_at": (
                record.candle_interval_started_at.isoformat()
                if record.candle_interval_started_at is not None
                else None
            ),
            "source": record.source,
            "direction": record.signal.direction.value,
            "strength": record.signal.strength.value,
            "reason": record.signal.reason,
            "disposition": record.disposition.value,
            "is_actionable": record.is_actionable,
            "is_duplicate_suppressed": (
                record.is_duplicate_suppressed
            ),
        }