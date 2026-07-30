from __future__ import annotations

from dataclasses import dataclass

from .classified_candle import ClassifiedCandle


@dataclass(
    frozen=True,
    slots=True,
)
class CandleSeries:
    """
    Representa una serie ordenada de velas clasificadas.
    """

    candles: tuple[ClassifiedCandle, ...]

    def __len__(
        self,
    ) -> int:
        return len(
            self.candles,
        )

    def is_empty(
        self,
    ) -> bool:
        return len(
            self.candles,
        ) == 0

    @property
    def first(
        self,
    ) -> ClassifiedCandle | None:
        if self.is_empty():
            return None

        return self.candles[0]

    @property
    def latest(
        self,
    ) -> ClassifiedCandle | None:
        if self.is_empty():
            return None

        return self.candles[-1]

    def without_latest(
        self,
    ) -> CandleSeries:
        """
        Devuelve una serie nueva sin la última vela visible.

        En el análisis en tiempo real, la última vela detectada se
        considera potencialmente abierta o todavía en formación.

        La instancia original no se modifica.
        """

        if self.is_empty():
            return self

        return CandleSeries(
            candles=self.candles[:-1],
        )