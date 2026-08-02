from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from pocket_option_analyzer.application.market.candle_interval_indicator_cache_status import (
    CandleIntervalIndicatorCacheStatus,
)
from pocket_option_analyzer.application.timing import (
    CandleIntervalKey,
    CandleIntervalResolver,
)
from pocket_option_analyzer.domain.indicators import (
    IndicatorSnapshot,
)

IndicatorSnapshotFactory = Callable[
    [],
    IndicatorSnapshot | None,
]


class CandleIntervalIndicatorCache:
    """
    Conserva un IndicatorSnapshot estable durante una vela.

    Comportamiento:

    - dentro del mismo intervalo devuelve el snapshot almacenado;
    - al comenzar una nueva vela conserva temporalmente el anterior;
    - después del margen calcula el nuevo snapshot;
    - si el nuevo cálculo falla, mantiene el último snapshot válido;
    - expone si ese snapshot pertenece realmente al intervalo actual.
    """

    def __init__(
        self,
        interval_resolver: CandleIntervalResolver | None = None,
        settling_seconds: float = 2.0,
    ) -> None:
        self._interval_resolver = interval_resolver or CandleIntervalResolver(
            duration_seconds=30,
        )

        if settling_seconds < 0:
            raise ValueError("settling_seconds no puede ser negativo.")

        if settling_seconds >= self._interval_resolver.duration_seconds:
            raise ValueError(
                "settling_seconds debe ser menor que la duración del intervalo."
            )

        self._settling_seconds = settling_seconds

        self._cached_key: CandleIntervalKey | None = None

        self._cached_snapshot: IndicatorSnapshot | None = None

        self._last_status: CandleIntervalIndicatorCacheStatus | None = None

    @property
    def cached_key(
        self,
    ) -> CandleIntervalKey | None:
        return self._cached_key

    @property
    def cached_snapshot(
        self,
    ) -> IndicatorSnapshot | None:
        return self._cached_snapshot

    @property
    def last_status(
        self,
    ) -> CandleIntervalIndicatorCacheStatus | None:
        """
        Estado resultante de la última llamada a resolve().
        """

        return self._last_status

    def resolve(
        self,
        observed_at: datetime,
        snapshot_factory: IndicatorSnapshotFactory,
    ) -> IndicatorSnapshot | None:
        """
        Devuelve el snapshot estable correspondiente al instante.

        El resultado puede ser un snapshot anterior. last_status permite
        determinar si está habilitado para generar señales accionables.
        """

        requested_key = self._interval_resolver.resolve(
            observed_at=observed_at,
        )

        if self._cached_snapshot is not None and requested_key == self._cached_key:
            self._set_status(
                requested_key=requested_key,
                is_current=True,
                is_settling=False,
            )

            return self._cached_snapshot

        if self._cached_snapshot is not None and self._is_settling(
            key=requested_key,
            observed_at=observed_at,
        ):
            self._set_status(
                requested_key=requested_key,
                is_current=False,
                is_settling=True,
            )

            return self._cached_snapshot

        candidate_snapshot = snapshot_factory()

        if candidate_snapshot is None:
            self._set_status(
                requested_key=requested_key,
                is_current=False,
                is_settling=False,
            )

            return self._cached_snapshot

        self._cached_key = requested_key
        self._cached_snapshot = candidate_snapshot

        self._set_status(
            requested_key=requested_key,
            is_current=True,
            is_settling=False,
        )

        return candidate_snapshot

    def reset(
        self,
    ) -> None:
        """
        Elimina el snapshot, la clave y el estado temporal.
        """

        self._cached_key = None
        self._cached_snapshot = None
        self._last_status = None

    def _set_status(
        self,
        requested_key: CandleIntervalKey,
        is_current: bool,
        is_settling: bool,
    ) -> None:
        self._last_status = CandleIntervalIndicatorCacheStatus(
            requested_key=requested_key,
            cached_key=self._cached_key,
            has_snapshot=(self._cached_snapshot is not None),
            is_current=is_current,
            is_settling=is_settling,
        )

    def _is_settling(
        self,
        key: CandleIntervalKey,
        observed_at: datetime,
    ) -> bool:
        return (
            key.elapsed_seconds(
                value=observed_at,
            )
            < self._settling_seconds
        )
