from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pocket_option_analyzer.domain.session_results import (
    ManualSignalResultRecord,
)


class ManualSignalResultSerializer:
    """
    Convierte resultados manuales a una estructura compatible con JSON.

    Todas las fechas se normalizan a UTC para facilitar análisis
    posteriores y evitar ambigüedades de zona horaria.
    """

    SCHEMA_VERSION = 1

    def serialize(
        self,
        record: ManualSignalResultRecord,
    ) -> dict[str, Any]:
        return {
            "schema_version": self.SCHEMA_VERSION,
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