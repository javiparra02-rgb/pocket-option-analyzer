from __future__ import annotations

from datetime import datetime

from pocket_option_analyzer.application.timing.candle_interval_key import (
    CandleIntervalKey,
)


class CandleIntervalResolver:
    """
    Alinea un instante con el intervalo de vela correspondiente.
    """

    def __init__(
        self,
        duration_seconds: int = 30,
    ) -> None:
        if duration_seconds < 1:
            raise ValueError("duration_seconds debe ser mayor o igual a 1.")

        if 60 % duration_seconds != 0:
            raise ValueError("duration_seconds debe dividir exactamente un minuto.")

        self._duration_seconds = duration_seconds

    @property
    def duration_seconds(
        self,
    ) -> int:
        return self._duration_seconds

    def resolve(
        self,
        observed_at: datetime,
    ) -> CandleIntervalKey:
        """
        Obtiene la clave temporal de la vela correspondiente.
        """

        aligned_second = observed_at.second - (
            observed_at.second % self._duration_seconds
        )

        started_at = observed_at.replace(
            second=aligned_second,
            microsecond=0,
        )

        return CandleIntervalKey(
            started_at=started_at,
            duration_seconds=self._duration_seconds,
        )
