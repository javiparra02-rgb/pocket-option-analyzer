from __future__ import annotations

from collections import deque

from pocket_option_analyzer.presentation.signals.signal_record_presenter import (
    SignalRecordViewModel,
)


class SessionSignalCounter:
    """
    Contador visual de señales confirmadas de la sesión actual.

    No persiste datos en disco.
    No modifica logs/signals.jsonl.
    No decide señales.

    Mantiene una cantidad limitada de claves recientes para evitar
    contar dos veces la misma señal sin acumular memoria indefinidamente.
    """

    DEFAULT_MAX_TRACKED_SIGNAL_KEYS = 256

    def __init__(
        self,
        max_tracked_signal_keys: int = (DEFAULT_MAX_TRACKED_SIGNAL_KEYS),
    ) -> None:
        if max_tracked_signal_keys < 1:
            raise ValueError("max_tracked_signal_keys debe ser mayor o igual a 1.")

        self._max_tracked_signal_keys = max_tracked_signal_keys

        self._call_count = 0
        self._put_count = 0

        self._counted_signal_keys: set[str] = set()

        self._counted_signal_key_order: deque[str] = deque()

    @property
    def call_count(
        self,
    ) -> int:
        return self._call_count

    @property
    def put_count(
        self,
    ) -> int:
        return self._put_count

    @property
    def total_count(
        self,
    ) -> int:
        return self._call_count + self._put_count

    @property
    def max_tracked_signal_keys(
        self,
    ) -> int:
        return self._max_tracked_signal_keys

    @property
    def tracked_signal_key_count(
        self,
    ) -> int:
        return len(
            self._counted_signal_keys,
        )

    @property
    def text(
        self,
    ) -> str:
        return (
            f"Sesión: {self._call_count} CALL | "
            f"{self._put_count} PUT | "
            f"{self.total_count} total"
        )

    def update(
        self,
        view_model: SignalRecordViewModel,
    ) -> None:
        if not view_model.is_actionable:
            return

        direction = view_model.direction_label.upper()

        if direction not in {
            "CALL",
            "PUT",
        }:
            return

        signal_key = self._build_signal_key(
            view_model=view_model,
        )

        if signal_key in self._counted_signal_keys:
            return

        self._remember_signal_key(
            signal_key=signal_key,
        )

        if direction == "CALL":
            self._call_count += 1
            return

        self._put_count += 1

    def reset(
        self,
    ) -> None:
        self._call_count = 0
        self._put_count = 0

        self._counted_signal_keys.clear()
        self._counted_signal_key_order.clear()

    def _remember_signal_key(
        self,
        signal_key: str,
    ) -> None:
        if len(self._counted_signal_key_order) >= self._max_tracked_signal_keys:
            oldest_key = self._counted_signal_key_order.popleft()

            self._counted_signal_keys.remove(
                oldest_key,
            )

        self._counted_signal_key_order.append(
            signal_key,
        )

        self._counted_signal_keys.add(
            signal_key,
        )

    def _build_signal_key(
        self,
        view_model: SignalRecordViewModel,
    ) -> str:
        return "|".join(
            (
                view_model.created_at_label,
                view_model.direction_label,
                view_model.source,
                view_model.operational_summary_label,
            )
        )
