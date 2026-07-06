from __future__ import annotations

from dataclasses import dataclass

from .signal_direction import SignalDirection
from .signal_strength import SignalStrength


@dataclass(frozen=True, slots=True)
class MarketSignal:
    """
    Señal generada por el motor de análisis.

    Esta clase representa únicamente una recomendación visual.
    No ejecuta operaciones ni interactúa con Pocket Option.
    """

    direction: SignalDirection

    strength: SignalStrength

    reason: str

    @property
    def is_actionable(self) -> bool:
        """
        Indica si la señal representa una posible acción CALL o PUT.
        """

        return self.direction in {
            SignalDirection.CALL,
            SignalDirection.PUT,
        }

    @classmethod
    def neutral(
        cls,
        reason: str = "No actionable signal detected.",
    ) -> MarketSignal:
        """
        Crea una señal neutral.
        """

        return cls(
            direction=SignalDirection.NONE,
            strength=SignalStrength.NONE,
            reason=reason,
        )