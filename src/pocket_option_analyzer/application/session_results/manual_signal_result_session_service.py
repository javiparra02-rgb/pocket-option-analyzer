from __future__ import annotations

from collections import deque
from collections.abc import Callable
from datetime import datetime, timezone
from uuid import uuid4

from pocket_option_analyzer.application.session_results.manual_signal_result_writer import (
    ManualSignalResultWriter,
)
from pocket_option_analyzer.domain.session_results import (
    ManualSignalResult,
    ManualSignalResultEventType,
    ManualSignalResultRecord,
)
from pocket_option_analyzer.domain.signals import (
    SignalDirection,
    SignalRecord,
)

Clock = Callable[[], datetime]
EventIdFactory = Callable[[], str]


def _utc_now() -> datetime:
    return datetime.now(
        timezone.utc,
    )


def _new_event_id() -> str:
    return uuid4().hex


class ManualSignalResultSessionService:
    """
    Asocia señales confirmadas con resultados manuales.

    Mantiene una cola FIFO de señales pendientes. El primer resultado
    registrado corresponde a la primera señal confirmada aún pendiente.

    La persistencia se realiza antes de modificar el estado en memoria.
    Si el escritor falla, la señal continúa pendiente.
    """

    DEFAULT_STRATEGY_NAME = "OTC_PRECISION_10S"

    def __init__(
        self,
        writer: ManualSignalResultWriter,
        clock: Clock = _utc_now,
        event_id_factory: EventIdFactory = _new_event_id,
        strategy_name: str = DEFAULT_STRATEGY_NAME,
    ) -> None:
        if not strategy_name.strip():
            raise ValueError(
                "strategy_name no puede estar vacío."
            )

        self._writer = writer
        self._clock = clock
        self._event_id_factory = event_id_factory
        self._strategy_name = strategy_name

        self._pending_signals: deque[SignalRecord] = deque()
        self._recorded_results: list[
            tuple[
                SignalRecord,
                ManualSignalResultRecord,
            ]
        ] = []

    @property
    def pending_count(self) -> int:
        return len(
            self._pending_signals,
        )

    @property
    def recorded_count(self) -> int:
        return len(
            self._recorded_results,
        )

    def track_confirmed_signal(
        self,
        record: SignalRecord,
    ) -> bool:
        """
        Agrega una señal confirmada a la cola de resultados pendientes.
        """

        if record.signal.direction not in {
            SignalDirection.CALL,
            SignalDirection.PUT,
        }:
            return False

        self._pending_signals.append(
            record,
        )

        return True

    def register_result(
        self,
        result: ManualSignalResult,
    ) -> ManualSignalResultRecord | None:
        """
        Registra el resultado de la señal pendiente más antigua.
        """

        if not self._pending_signals:
            return None

        signal_record = self._pending_signals[0]

        result_record = ManualSignalResultRecord(
            signal_created_at=signal_record.created_at,
            direction=signal_record.signal.direction,
            strength=signal_record.signal.strength,
            result=result,
            registered_at=self._clock(),
            source=signal_record.source,
            reason=signal_record.signal.reason,
            strategy_name=self._strategy_name,
            event_id=self._event_id_factory(),
            event_type=ManualSignalResultEventType.RECORDED,
        )

        self._writer.append(
            record=result_record,
        )

        self._pending_signals.popleft()
        self._recorded_results.append(
            (
                signal_record,
                result_record,
            )
        )

        return result_record

    def undo_last_result(
        self,
    ) -> ManualSignalResultRecord | None:
        """
        Persiste una reversión y vuelve a dejar pendiente la señal.
        """

        if not self._recorded_results:
            return None

        signal_record, original_record = self._recorded_results[-1]

        reversal_record = ManualSignalResultRecord(
            signal_created_at=original_record.signal_created_at,
            direction=original_record.direction,
            strength=original_record.strength,
            result=original_record.result,
            registered_at=self._clock(),
            source=original_record.source,
            reason=original_record.reason,
            strategy_name=original_record.strategy_name,
            event_id=self._event_id_factory(),
            event_type=ManualSignalResultEventType.REVERSED,
            reverses_event_id=original_record.event_id,
        )

        self._writer.append(
            record=reversal_record,
        )

        self._recorded_results.pop()
        self._pending_signals.appendleft(
            signal_record,
        )

        return reversal_record

    def reset(
        self,
    ) -> None:
        """
        Limpia solamente el estado temporal de la sesión.

        No elimina eventos ya escritos en JSONL.
        """

        self._pending_signals.clear()
        self._recorded_results.clear()