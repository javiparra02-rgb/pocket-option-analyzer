from __future__ import annotations

from dataclasses import dataclass

from pocket_option_analyzer.application.timing import (
    CandleIntervalKey,
)


@dataclass(
    frozen=True,
    slots=True,
)
class CandleIntervalIndicatorCacheStatus:
    """
    Describe la relación temporal entre el intervalo solicitado
    y el IndicatorSnapshot actualmente almacenado.

    ACTUAL:
        El snapshot pertenece a la vela solicitada.

    ESTABILIZANDO:
        Comenzó una vela nueva, pero todavía se conserva temporalmente
        el snapshot anterior durante el margen de estabilización.

    DESACTUALIZADO:
        Terminó el margen de estabilización, pero no fue posible
        construir todavía un snapshot para la vela actual.

    NO_DISPONIBLE:
        No existe ningún snapshot válido.
    """

    requested_key: CandleIntervalKey

    cached_key: CandleIntervalKey | None

    has_snapshot: bool

    is_current: bool

    is_settling: bool

    def __post_init__(
        self,
    ) -> None:
        if (
            self.has_snapshot
            and self.cached_key is None
        ):
            raise ValueError(
                "Un snapshot existente debe incluir cached_key."
            )

        if (
            not self.has_snapshot
            and self.cached_key is not None
        ):
            raise ValueError(
                "cached_key no puede existir sin snapshot."
            )

        if self.is_current:
            if not self.has_snapshot:
                raise ValueError(
                    "Un estado actual debe contener un snapshot."
                )

            if self.cached_key != self.requested_key:
                raise ValueError(
                    "Un snapshot actual debe pertenecer "
                    "al intervalo solicitado."
                )

        if self.is_settling:
            if not self.has_snapshot:
                raise ValueError(
                    "La estabilización requiere un snapshot anterior."
                )

            if self.is_current:
                raise ValueError(
                    "Un snapshot actual no puede estar estabilizando."
                )

            if self.cached_key == self.requested_key:
                raise ValueError(
                    "La estabilización requiere un intervalo "
                    "almacenado diferente del solicitado."
                )

    @property
    def state_label(
        self,
    ) -> str:
        if self.is_current:
            return "ACTUAL"

        if self.is_settling:
            return "ESTABILIZANDO"

        if self.has_snapshot:
            return "DESACTUALIZADO"

        return "NO_DISPONIBLE"

    @property
    def allows_actionable_signals(
        self,
    ) -> bool:
        """
        Solo un snapshot perteneciente al intervalo actual puede
        participar en una CALL o PUT confirmada.
        """

        return self.is_current