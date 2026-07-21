from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pocket_option_analyzer.domain.session_results import (
    ManualSignalResultRecord,
)


class ManualSignalResultSerializer:
    """
    Convierte eventos de resultados manuales a JSON.

    Las fechas se normalizan a UTC.
    """

    SCHEMA_VERSION = 2

    def serialize(
        self,
        record: ManualSignalResultRecord,
    ) -> dict[str, Any]:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "event_id": record.event_id,
            "event_type": record.event_type.value,
            "reverses_event_id": record.reverses_event_id,
            "strategy": record.strategy_name,
            "signal_created_at": self._format_datetime(
                value=record.signal_created_at,
            ),
            "direction": record.direction.value,
            "strength": record.strength.value,
            "result": record.result.value,
            "registered_at": self._format_datetime(
                value=record.registered_at,
            ),
            "source": record.source,
            "reason": record.reason,
        }

    @staticmethod
    def _format_datetime(
        value: datetime,
    ) -> str:
        utc_value = value.astimezone(
            timezone.utc,
        )

        return (
            utc_value.isoformat()
            .replace(
                "+00:00",
                "Z",
            )
        )