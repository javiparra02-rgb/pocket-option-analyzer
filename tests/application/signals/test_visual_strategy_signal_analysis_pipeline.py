import numpy as np

from pocket_option_analyzer.application.signals import (
    VisualStrategySignalAnalysisPipeline,
)
from pocket_option_analyzer.domain.indicators import (
    EmaSnapshot,
    IndicatorSnapshot,
    RsiSnapshot,
    StochasticCalculationDiagnostics,
    StochasticSnapshot,
)
from pocket_option_analyzer.domain.signals import (
    MarketSignal,
    SignalDirection,
    SignalStrength,
)
from pocket_option_analyzer.domain.strategy import StrategyProfile
from pocket_option_analyzer.vision.models import (
    CandleCandidate,
    CandleGeometry,
    CandleSeries,
    CandleType,
    ClassifiedCandle,
    MarketAnalysis,
    TrendDirection,
)


class FakeMarketAnalysisPipeline:

    def __init__(
        self,
        result: MarketAnalysis,
    ) -> None:
        self.result = result
        self.received_image = None

    def analyze(
        self,
        image,
    ) -> MarketAnalysis:
        self.received_image = image
        return self.result


class FakeVisualIndicatorSnapshotBuilder:

    def __init__(
        self,
        result: IndicatorSnapshot | None,
    ) -> None:
        self.result = result
        self.received_series = None
        self.received_profile = None

    def build(
        self,
        series,
        profile,
    ) -> IndicatorSnapshot | None:
        self.received_series = series
        self.received_profile = profile
        return self.result


class FakeStrategySignalGenerator:

    def __init__(
        self,
        result: MarketSignal,
    ) -> None:
        self.result = result
        self.received_analysis = None
        self.received_indicators = None
        self.was_called = False

    def generate(
        self,
        analysis,
        indicators,
    ) -> MarketSignal:
        self.was_called = True
        self.received_analysis = analysis
        self.received_indicators = indicators
        return self.result


def _visual_series() -> CandleSeries:

    return CandleSeries(
        candles=(
            ClassifiedCandle(
                candidate=CandleCandidate(
                    x=10,
                    y=40,
                    width=5,
                    height=20,
                    area=100,
                    geometry=CandleGeometry(
                        high_y=40,
                        body_top_y=45,
                        body_bottom_y=54,
                        low_y=59,
                    ),
                ),
                candle_type=CandleType.BULLISH,
            ),
            ClassifiedCandle(
                candidate=CandleCandidate(
                    x=20,
                    y=35,
                    width=5,
                    height=25,
                    area=125,
                    geometry=CandleGeometry(
                        high_y=35,
                        body_top_y=40,
                        body_bottom_y=54,
                        low_y=59,
                    ),
                ),
                candle_type=CandleType.BEARISH,
            ),
        ),
    )


def _market_analysis() -> MarketAnalysis:

    return MarketAnalysis(
        series=_visual_series(),
        trend=TrendDirection.BULLISH,
    )


def _indicators() -> IndicatorSnapshot:

    return IndicatorSnapshot(
        ema=EmaSnapshot(
            fast_value=105.0,
            slow_value=100.0,
            separation_candles=3,
        ),
        rsi=RsiSnapshot(
            value=57.0,
        ),
        stochastic=StochasticSnapshot(
            k_previous=18.0,
            d_previous=20.0,
            k_value=24.0,
            d_value=21.0,
            diagnostics=StochasticCalculationDiagnostics(
                source_candle_count=1,
                k_period=5,
                highest_high=120.0,
                lowest_low=80.0,
                latest_close=104.0,
                latest_raw_k=60.0,
                latest_smoothed_k=24.0,
                latest_d=21.0,
            ),
        ),
    )


def test_analyze_generates_signal_from_visual_indicators() -> None:

    image = np.zeros(
        (100, 100, 3),
        dtype=np.uint8,
    )

    analysis = _market_analysis()
    indicators = _indicators()
    profile = StrategyProfile.otc_precision_10s()

    market_pipeline = FakeMarketAnalysisPipeline(
        result=analysis,
    )
    indicator_builder = FakeVisualIndicatorSnapshotBuilder(
        result=indicators,
    )
    signal_generator = FakeStrategySignalGenerator(
        result=MarketSignal(
            direction=SignalDirection.CALL,
            strength=SignalStrength.HIGH,
            reason="Strategy conditions confirmed.",
        ),
    )

    pipeline = VisualStrategySignalAnalysisPipeline(
        market_analysis_pipeline=market_pipeline,
        indicator_snapshot_builder=indicator_builder,
        signal_generator=signal_generator,
        profile=profile,
    )

    result = pipeline.analyze(
        image=image,
    )

    assert result.direction is SignalDirection.CALL
    assert result.strength is SignalStrength.HIGH
    assert market_pipeline.received_image is image
    assert indicator_builder.received_series is analysis.series
    assert indicator_builder.received_profile is profile
    assert signal_generator.received_analysis is analysis
    assert signal_generator.received_indicators is indicators
    assert (
        "Auditoría Stoch ventana: "
        "visibles=2 | OHLC cerradas=1 | "
        "K-periodo=5 | geometría=1/1"
        in result.reason
    )
    assert (
        "Auditoría Stoch OHLC: "
        "máximo=120.00 | mínimo=80.00 | "
        "cierre=104.00 | rango=40.00"
        in result.reason
    )
    assert (
        "Auditoría Stoch cálculo: "
        "K bruto=60.00 | K suavizado=24.00 | D=21.00"
        in result.reason
    )


def test_analyze_returns_neutral_signal_when_indicators_are_missing() -> None:

    signal_generator = FakeStrategySignalGenerator(
        result=MarketSignal(
            direction=SignalDirection.CALL,
            strength=SignalStrength.HIGH,
            reason="Should not be used.",
        ),
    )

    pipeline = VisualStrategySignalAnalysisPipeline(
        market_analysis_pipeline=FakeMarketAnalysisPipeline(
            result=_market_analysis(),
        ),
        indicator_snapshot_builder=FakeVisualIndicatorSnapshotBuilder(
            result=None,
        ),
        signal_generator=signal_generator,
        profile=StrategyProfile.otc_precision_10s(),
    )

    result = pipeline.analyze(
        image=np.zeros(
            (100, 100, 3),
            dtype=np.uint8,
        ),
    )

    assert result.direction is SignalDirection.NONE
    assert result.is_actionable is False
    assert "[visual_diagnostics]" in result.reason
    assert "Diagnóstico visual:" in result.reason
    assert "Tendencia:" in result.reason
    assert "Velas detectadas:" in result.reason
    assert "Últimas:" in result.reason
    assert "Cerradas:" in result.reason
    assert "Direccionales:" in result.reason
    assert "Contexto:" in result.reason
    assert "Vigilancia:" in result.reason
    assert "Estado:" in result.reason
    assert "[indicator_diagnostics]" in result.reason
    assert "Diagnóstico de indicadores:" in result.reason
    assert "EMA: no disponible" in result.reason
    assert "RSI: no disponible" in result.reason
    assert "Stochastic: no disponible" in result.reason
    assert "Estado: velas insuficientes" in result.reason
    assert (
        "Not enough visual candles to calculate indicators."
        in result.reason
    )
    assert "Minimum visible required: 14." in result.reason
    assert "Minimum closed required: 13." in result.reason