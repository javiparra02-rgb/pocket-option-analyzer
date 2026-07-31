from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(
    frozen=True,
    slots=True,
)
class CandleIntervalKey:
    """
    Identifica un intervalo temporal de vela.

    Para velas de 30 segundos, ejemplos válidos:

    - 16:44:00 a 16:44:29.999...
    - 16:44:30 a 16:44:59.999...

    La zona horaria del datetime original se conserva.
    """

    started_at: datetime
    duration_seconds: int = 30

    def __post_init__(
        self,
    ) -> None:
        if self.duration_seconds < 1:
            raise ValueError(
                "duration_seconds debe ser mayor o igual a 1."
            )

        if 60 % self.duration_seconds != 0:
            raise ValueError(
                "duration_seconds debe dividir exactamente un minuto."
            )

        if self.started_at.microsecond != 0:
            raise ValueError(
                "started_at debe estar alineado sin microsegundos."
            )

        if (
            self.started_at.second
            % self.duration_seconds
            != 0
        ):
            raise ValueError(
                "started_at no está alineado con la duración."
            )

    @property
    def ends_at(
        self,
    ) -> datetime:
        """
        Primer instante perteneciente al intervalo siguiente.
        """

        return (
            self.started_at
            + timedelta(
                seconds=self.duration_seconds,
            )
        )

    def contains(
        self,
        value: datetime,
    ) -> bool:
        """
        Indica si el instante pertenece a este intervalo.
        """

        return (
            self.started_at
            <= value
            < self.ends_at
        )

    def elapsed_seconds(
        self,
        value: datetime,
    ) -> float:
        """
        Segundos transcurridos desde el inicio del intervalo.
        """

        return (
            value
            - self.started_at
        ).total_seconds()