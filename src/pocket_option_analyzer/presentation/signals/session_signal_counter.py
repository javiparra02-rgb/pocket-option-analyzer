from __future__ import annotations

from pocket_option_analyzer.presentation.signals.signal_record_presenter import (
    SignalRecordViewModel,
)


class SessionSignalCounter:
    """
    Contador visual de señales confirmadas de la sesión actual.

    No persiste datos en disco.
    No modifica logs/signals.jsonl.
    No decide señales.
    Solo cuenta señales accionables CALL/PUT mientras la app está abierta.
    """

    def __init__(
        self,
    ) -> None:
        self._call_count = 0
        self._put_count = 0
        self._counted_signal_keys: set[str] = set()

    @property
    def call_count(self) -> int:
        return self._call_count

    @property
    def put_count(self) -> int:
        return self._put_count

    @property
    def total_count(self) -> int:
        return self._call_count + self._put_count

    @property
    def text(self) -> str:
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

        if direction not in {"CALL", "PUT"}:
            return

        signal_key = self._build_signal_key(
            view_model=view_model,
        )

        if signal_key in self._counted_signal_keys:
            return

        self._counted_signal_keys.add(
            signal_key,
        )

        if direction == "CALL":
            self._call_count += 1
            return

        if direction == "PUT":
            self._put_count += 1

    def reset(
        self,
    ) -> None:
        self._call_count = 0
        self._put_count = 0
        self._counted_signal_keys.clear()

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