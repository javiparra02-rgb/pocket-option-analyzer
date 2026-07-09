from pocket_option_analyzer.application.market import (
    VisualEntryContextAnalyzer,
)
from pocket_option_analyzer.vision.models import (
    CandleCandidate,
    CandleSeries,
    CandleType,
    ClassifiedCandle,
    MarketAnalysis,
    TrendDirection,
)


def _classified(
    x: int,
    candle_type: CandleType,
) -> ClassifiedCandle:

    return ClassifiedCandle(
        candidate=CandleCandidate(
            x=x,
            y=10,
            width=10,
            height=40,
            area=400,
        ),
        candle_type=candle_type,
    )


def _analysis(
    trend: TrendDirection,
    candle_types,
) -> MarketAnalysis:

    return MarketAnalysis(
        series=CandleSeries(
            candles=tuple(
                _classified(
                    x=index,
                    candle_type=candle_type,
                )
                for index, candle_type in enumerate(
                    candle_types,
                )
            ),
        ),
        trend=trend,
    )


def test_visual_entry_context_analyzer_detects_bearish_continuation() -> None:

    analyzer = VisualEntryContextAnalyzer(
        recent_closed_candles=3,
        ignore_latest_candle=True,
    )

    context = analyzer.analyze(
        analysis=_analysis(
            trend=TrendDirection.BEARISH,
            candle_types=[
                CandleType.BEARISH,
                CandleType.BEARISH,
                CandleType.BEARISH,
                CandleType.BULLISH,
            ],
        ),
    )

    assert context.context_label == "BEARISH_CONTINUATION"
    assert context.entry_state_label == "BUSCAR_PUT"


def test_visual_entry_context_analyzer_detects_bearish_pullback() -> None:

    analyzer = VisualEntryContextAnalyzer(
        recent_closed_candles=3,
        ignore_latest_candle=True,
    )

    context = analyzer.analyze(
        analysis=_analysis(
            trend=TrendDirection.BEARISH,
            candle_types=[
                CandleType.BULLISH,
                CandleType.BULLISH,
                CandleType.BEARISH,
                CandleType.BEARISH,
            ],
        ),
    )

    assert context.context_label == "BEARISH_PULLBACK"
    assert context.entry_state_label == "ESPERAR"


def test_visual_entry_context_analyzer_detects_bullish_continuation() -> None:

    analyzer = VisualEntryContextAnalyzer(
        recent_closed_candles=3,
        ignore_latest_candle=True,
    )

    context = analyzer.analyze(
        analysis=_analysis(
            trend=TrendDirection.BULLISH,
            candle_types=[
                CandleType.BULLISH,
                CandleType.BULLISH,
                CandleType.BULLISH,
                CandleType.BEARISH,
            ],
        ),
    )

    assert context.context_label == "BULLISH_CONTINUATION"
    assert context.entry_state_label == "BUSCAR_CALL"


def test_visual_entry_context_analyzer_detects_bullish_pullback() -> None:

    analyzer = VisualEntryContextAnalyzer(
        recent_closed_candles=3,
        ignore_latest_candle=True,
    )

    context = analyzer.analyze(
        analysis=_analysis(
            trend=TrendDirection.BULLISH,
            candle_types=[
                CandleType.BEARISH,
                CandleType.BEARISH,
                CandleType.BULLISH,
                CandleType.BULLISH,
            ],
        ),
    )

    assert context.context_label == "BULLISH_PULLBACK"
    assert context.entry_state_label == "ESPERAR"


def test_visual_entry_context_analyzer_detects_sideways_market() -> None:

    analyzer = VisualEntryContextAnalyzer()

    context = analyzer.analyze(
        analysis=_analysis(
            trend=TrendDirection.SIDEWAYS,
            candle_types=[
                CandleType.BULLISH,
                CandleType.BEARISH,
                CandleType.DOJI,
            ],
        ),
    )

    assert context.context_label == "SIDEWAYS_MARKET"
    assert context.entry_state_label == "ESPERAR"