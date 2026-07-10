from __future__ import annotations

from pocket_option_analyzer.application.market.visual_entry_context import (
    VisualEntryContext,
)
from pocket_option_analyzer.vision.models import (
    CandleType,
    ClassifiedCandle,
    MarketAnalysis,
    TrendDirection,
)


class VisualEntryContextAnalyzer:
    """
    Analiza el contexto visual reciente del gráfico.

    Separa:
    - tendencia general
    - reacción reciente
    - estado de vigilancia

    Para evitar ruido, ignora velas UNKNOWN y DOJI.
    """

    def __init__(
        self,
        recent_closed_candles: int = 3,
        ignore_latest_candle: bool = True,
    ) -> None:
        self._recent_closed_candles = recent_closed_candles
        self._ignore_latest_candle = ignore_latest_candle

    def analyze(
        self,
        analysis: MarketAnalysis,
    ) -> VisualEntryContext:

        recent_candles = self._recent_directional_candles(
            analysis=analysis,
        )

        if not recent_candles:
            return VisualEntryContext(
                context_label="NO_DIRECTIONAL_CANDLES",
                entry_state_label="ESPERAR",
            )

        bearish_count = self._count_type(
            candles=recent_candles,
            candle_type=CandleType.BEARISH,
        )
        bullish_count = self._count_type(
            candles=recent_candles,
            candle_type=CandleType.BULLISH,
        )

        if analysis.trend is TrendDirection.BEARISH:
            return self._bearish_context(
                bearish_count=bearish_count,
                bullish_count=bullish_count,
            )

        if analysis.trend is TrendDirection.BULLISH:
            return self._bullish_context(
                bearish_count=bearish_count,
                bullish_count=bullish_count,
            )

        if analysis.trend is TrendDirection.SIDEWAYS:
            return VisualEntryContext(
                context_label="SIDEWAYS_MARKET",
                entry_state_label="ESPERAR",
            )

        return VisualEntryContext(
            context_label="UNKNOWN_TREND",
            entry_state_label="ESPERAR",
        )

    def _bearish_context(
        self,
        bearish_count: int,
        bullish_count: int,
    ) -> VisualEntryContext:

        if bearish_count > bullish_count:
            return VisualEntryContext(
                context_label="BEARISH_CONTINUATION",
                entry_state_label="BUSCAR_PUT",
            )

        if bullish_count > bearish_count:
            return VisualEntryContext(
                context_label="BEARISH_PULLBACK",
                entry_state_label="ESPERAR",
            )

        return VisualEntryContext(
            context_label="BEARISH_INDECISION",
            entry_state_label="ESPERAR",
        )

    def _bullish_context(
        self,
        bearish_count: int,
        bullish_count: int,
    ) -> VisualEntryContext:

        if bullish_count > bearish_count:
            return VisualEntryContext(
                context_label="BULLISH_CONTINUATION",
                entry_state_label="BUSCAR_CALL",
            )

        if bearish_count > bullish_count:
            return VisualEntryContext(
                context_label="BULLISH_PULLBACK",
                entry_state_label="ESPERAR",
            )

        return VisualEntryContext(
            context_label="BULLISH_INDECISION",
            entry_state_label="ESPERAR",
        )

    def _recent_directional_candles(
        self,
        analysis: MarketAnalysis,
    ) -> tuple[ClassifiedCandle, ...]:

        candles = tuple(
            analysis.series.candles,
        )

        if self._ignore_latest_candle and len(candles) > 1:
            candles = candles[:-1]

        directional_candles = tuple(
            candle
            for candle in candles
            if candle.candle_type
            in {
                CandleType.BULLISH,
                CandleType.BEARISH,
            }
        )

        return directional_candles[
            -self._recent_closed_candles :
        ]

    def _count_type(
        self,
        candles: tuple[ClassifiedCandle, ...],
        candle_type: CandleType,
    ) -> int:

        return sum(
            1
            for candle in candles
            if candle.candle_type is candle_type
        )