from __future__ import annotations

from dataclasses import dataclass

from .candle_color import CandleColor


@dataclass(frozen=True, slots=True)
class CandleColorProfile:
    """
    Define qué color representa una vela bullish
    y qué color representa una vela bearish.
    """

    bullish: CandleColor
    bearish: CandleColor

    @classmethod
    def green_red(cls) -> CandleColorProfile:
        """
        Perfil clásico: velas alcistas verdes y bajistas rojas.
        """

        return cls(
            bullish=CandleColor.GREEN,
            bearish=CandleColor.RED,
        )

    @classmethod
    def white_red(cls) -> CandleColorProfile:
        """
        Perfil usado en gráficos donde las velas alcistas son blancas
        y las bajistas son rojas.
        """

        return cls(
            bullish=CandleColor.WHITE,
            bearish=CandleColor.RED,
        )