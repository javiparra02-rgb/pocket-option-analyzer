from __future__ import annotations

from typing import Any

from pocket_option_analyzer.domain.signals import (
    SignalRecord,
)
from pocket_option_analyzer.infrastructure.signals.duplicate_signal_summary import (
    DuplicateSignalSummary,
)


class SignalRecordSerializer:
    """
    Convierte registros y resúmenes en estructuras serializables.

    Representaciones:

    - full:
      registro técnico completo;

    - summary:
      resumen acumulado de señales duplicadas de una vela.
    """

    def to_dict(
        self,
        record: SignalRecord,
    ) -> dict[str, Any]:
        """
        Serializa un SignalRecord completo.
        """

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
            "is_duplicate_suppressed": (record.is_duplicate_suppressed),
            "storage_format": "full",
        }

    def to_duplicate_summary_dict(
        self,
        summary: DuplicateSignalSummary,
    ) -> dict[str, Any]:
        """
        Serializa el resumen único de duplicados de una vela.
        """

        return {
            "event_type": "duplicate_signal_summary",
            "created_at": (summary.last_duplicate_at.isoformat()),
            "candle_interval_started_at": (
                summary.candle_interval_started_at.isoformat()
            ),
            "source": summary.source,
            "accepted_direction": (summary.accepted_direction.value),
            "accepted_record_found": (summary.accepted_record_found),
            "disposition": "duplicate_suppressed",
            "duplicate_suppressed_count": (summary.duplicate_suppressed_count),
            "duplicate_direction_counts": {
                "call": summary.call_duplicate_count,
                "put": summary.put_duplicate_count,
            },
            "first_duplicate_at": (summary.first_duplicate_at.isoformat()),
            "last_duplicate_at": (summary.last_duplicate_at.isoformat()),
            "is_actionable": False,
            "is_duplicate_suppressed": True,
            "storage_format": "summary",
        }
