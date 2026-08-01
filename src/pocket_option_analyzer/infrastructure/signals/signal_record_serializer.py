from __future__ import annotations

from typing import Any

from pocket_option_analyzer.domain.signals import (
    SignalRecord,
)


class SignalRecordSerializer:
    """
    Convierte SignalRecord en estructuras serializables.

    Existen dos representaciones:

    - completa: conserva el diagnóstico técnico;
    - compacta: conserva solamente los datos necesarios
      para auditar una repetición suprimida.
    """

    def to_dict(
        self,
        record: SignalRecord,
    ) -> dict[str, Any]:
        """
        Serializa un registro completo.

        Se utiliza para:

        - primera observación de cada vela;
        - señales accionables aceptadas.
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
            "is_duplicate_suppressed": (
                record.is_duplicate_suppressed
            ),
            "storage_format": "full",
        }

    def to_compact_dict(
        self,
        record: SignalRecord,
    ) -> dict[str, Any]:
        """
        Serializa una repetición del gate sin copiar nuevamente
        todo el diagnóstico técnico.

        La señal aceptada del mismo intervalo conserva previamente
        el diagnóstico completo.
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
            "disposition": record.disposition.value,
            "is_actionable": record.is_actionable,
            "is_duplicate_suppressed": (
                record.is_duplicate_suppressed
            ),
            "storage_format": "compact",
        }