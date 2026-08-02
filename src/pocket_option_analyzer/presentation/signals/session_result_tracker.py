from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SessionResult(StrEnum):
    """
    Resultado manual asociado a una señal operada.

    El programa no intenta obtener este resultado desde Pocket Option.
    El usuario lo registra manualmente.
    """

    WIN = "WIN"
    LOSS = "LOSS"


@dataclass(
    frozen=True,
    slots=True,
)
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

    Mantiene contadores incrementales para que las estadísticas y los
    snapshots no tengan que recorrer todo el historial continuamente.

    El historial completo se conserva durante la sesión para permitir
    deshacer resultados consecutivamente y reconstruir correctamente
    las rachas de pérdidas.
    """

    DEFAULT_MAX_CONSECUTIVE_LOSSES = 3

    def __init__(
        self,
        max_consecutive_losses: int = (DEFAULT_MAX_CONSECUTIVE_LOSSES),
    ) -> None:
        if max_consecutive_losses < 1:
            raise ValueError("max_consecutive_losses debe ser mayor o igual a 1.")

        self._max_consecutive_losses = max_consecutive_losses

        self._history: list[SessionResult] = []

        self._wins = 0
        self._losses = 0
        self._consecutive_losses = 0

    @property
    def wins(
        self,
    ) -> int:
        return self._wins

    @property
    def losses(
        self,
    ) -> int:
        return self._losses

    @property
    def total(
        self,
    ) -> int:
        return self._wins + self._losses

    @property
    def consecutive_losses(
        self,
    ) -> int:
        return self._consecutive_losses

    @property
    def max_consecutive_losses(
        self,
    ) -> int:
        return self._max_consecutive_losses

    @property
    def win_rate_percentage(
        self,
    ) -> float | None:
        if self.total == 0:
            return None

        return self._wins / self.total * 100.0

    @property
    def pause_recommended(
        self,
    ) -> bool:
        return self._consecutive_losses >= self._max_consecutive_losses

    @property
    def history(
        self,
    ) -> tuple[SessionResult, ...]:
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

        self._wins += 1
        self._consecutive_losses = 0

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

        self._losses += 1
        self._consecutive_losses += 1

        return self.snapshot()

    def undo_last_result(
        self,
    ) -> SessionResult | None:
        """
        Elimina el último resultado registrado.

        Actualiza los contadores y reconstruye la racha de pérdidas
        utilizando los resultados que permanecen en la sesión.

        Retorna el resultado eliminado o None si el historial está vacío.
        """

        if not self._history:
            return None

        removed_result = self._history.pop()

        if removed_result is SessionResult.WIN:
            self._wins -= 1
        else:
            self._losses -= 1

        self._recalculate_consecutive_losses()

        return removed_result

    def reset(
        self,
    ) -> None:
        """
        Reinicia completamente los resultados de la sesión.
        """

        self._history.clear()

        self._wins = 0
        self._losses = 0
        self._consecutive_losses = 0

    def snapshot(
        self,
    ) -> SessionResultSnapshot:
        """
        Construye una representación inmutable del estado actual.
        """

        return SessionResultSnapshot(
            wins=self._wins,
            losses=self._losses,
            total=self.total,
            consecutive_losses=(self._consecutive_losses),
            max_consecutive_losses=(self._max_consecutive_losses),
            win_rate_percentage=(self.win_rate_percentage),
            pause_recommended=(self.pause_recommended),
        )

    def _recalculate_consecutive_losses(
        self,
    ) -> None:
        """
        Reconstruye la racha final después de deshacer un resultado.

        Este recorrido solo ocurre durante undo, no durante las
        actualizaciones y consultas normales de la GUI.
        """

        consecutive_losses = 0

        for result in reversed(
            self._history,
        ):
            if result is not SessionResult.LOSS:
                break

            consecutive_losses += 1

        self._consecutive_losses = consecutive_losses
