from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SessionResult(str, Enum):
    """
    Resultado manual asociado a una señal operada.

    El programa no intenta obtener este resultado desde Pocket Option.
    El usuario lo registra manualmente.
    """

    WIN = "WIN"
    LOSS = "LOSS"


@dataclass(frozen=True)
class SessionResultSnapshot:
    """
    Estado inmutable de los resultados de la sesión.
    """

    wins: int
    losses: int
    total: int
    consecutive_losses: int
    max_consecutive_losses: int
    win_rate_percentage: float | None
    pause_recommended: bool


class SessionResultTracker:
    """
    Registra manualmente resultados de señales durante una sesión.

    No consulta Pocket Option.
    No ejecuta operaciones.
    No determina automáticamente si una señal ganó o perdió.
    """

    DEFAULT_MAX_CONSECUTIVE_LOSSES = 3

    def __init__(
        self,
        max_consecutive_losses: int = DEFAULT_MAX_CONSECUTIVE_LOSSES,
    ) -> None:
        if max_consecutive_losses < 1:
            raise ValueError("max_consecutive_losses debe ser mayor o igual a 1.")

        self._max_consecutive_losses = max_consecutive_losses
        self._history: list[SessionResult] = []

    @property
    def wins(self) -> int:
        return self._history.count(
            SessionResult.WIN,
        )

    @property
    def losses(self) -> int:
        return self._history.count(
            SessionResult.LOSS,
        )

    @property
    def total(self) -> int:
        return len(
            self._history,
        )

    @property
    def consecutive_losses(self) -> int:
        loss_count = 0

        for result in reversed(
            self._history,
        ):
            if result != SessionResult.LOSS:
                break

            loss_count += 1

        return loss_count

    @property
    def max_consecutive_losses(self) -> int:
        return self._max_consecutive_losses

    @property
    def win_rate_percentage(self) -> float | None:
        if self.total == 0:
            return None

        return self.wins / self.total * 100.0

    @property
    def pause_recommended(self) -> bool:
        return self.consecutive_losses >= self._max_consecutive_losses

    @property
    def history(self) -> tuple[SessionResult, ...]:
        return tuple(
            self._history,
        )

    def register_win(
        self,
    ) -> SessionResultSnapshot:
        """
        Registra manualmente una operación ganada.

        Una ganada reinicia la racha consecutiva de pérdidas.
        """

        self._history.append(
            SessionResult.WIN,
        )

        return self.snapshot()

    def register_loss(
        self,
    ) -> SessionResultSnapshot:
        """
        Registra manualmente una operación perdida.
        """

        self._history.append(
            SessionResult.LOSS,
        )

        return self.snapshot()

    def undo_last_result(
        self,
    ) -> SessionResult | None:
        """
        Elimina el último resultado registrado.

        Retorna el resultado eliminado o None si el historial está vacío.
        """

        if not self._history:
            return None

        return self._history.pop()

    def reset(
        self,
    ) -> None:
        """
        Reinicia completamente los resultados de la sesión.
        """

        self._history.clear()

    def snapshot(
        self,
    ) -> SessionResultSnapshot:
        """
        Construye una representación inmutable del estado actual.
        """

        return SessionResultSnapshot(
            wins=self.wins,
            losses=self.losses,
            total=self.total,
            consecutive_losses=self.consecutive_losses,
            max_consecutive_losses=self._max_consecutive_losses,
            win_rate_percentage=self.win_rate_percentage,
            pause_recommended=self.pause_recommended,
        )
