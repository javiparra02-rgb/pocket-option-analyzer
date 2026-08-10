from datetime import UTC, datetime

import numpy as np

from pocket_option_analyzer.application.market import (
    CandleIntervalIndicatorCacheStatus,
    VisualIndicatorSnapshotContext,
)
from pocket_option_analyzer.application.signals import (
    StrategySignalGenerator,
    VisualStrategySignalAnalysisPipeline,
)
from pocket_option_analyzer.application.strategy import StrategyConditionEvaluator
from pocket_option_analyzer.application.timing import (
    CandleIntervalKey,
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
    CandleFilterDiagnostics,
    CandleGeometry,
    CandleSeries,
    CandleType,
    ClassifiedCandle,
    CurrentVisualPrice,
    CurrentVisualPriceExtraction,
    CurrentVisualPriceStatus,
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
        self.received_price_observation_image = None

    def analyze(
        self,
        image,
        price_observation_image=None,
    ) -> MarketAnalysis:
        self.received_image = image
        self.received_price_observation_image = price_observation_image
        return self.result


class FakeVisualIndicatorSnapshotBuilder:
    def __init__(
        self,
        result: IndicatorSnapshot | None,
        snapshot_context: (VisualIndicatorSnapshotContext | None) = None,
        snapshot_timing_status: (CandleIntervalIndicatorCacheStatus | None) = None,
    ) -> None:
        self.result = result
        self.snapshot_context = snapshot_context
        self.received_series = None
        self.received_profile = None
        self.snapshot_timing_status = snapshot_timing_status

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
        snapshot_context=VisualIndicatorSnapshotContext(
            visible_candle_count=2,
            ohlc_candle_count=1,
            geometry_valid_count=1,
            geometry_total_count=1,
        ),
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
    assert market_pipeline.received_price_observation_image is None
    assert indicator_builder.received_series is analysis.series
    assert indicator_builder.received_profile is profile
    assert signal_generator.received_analysis is analysis
    assert signal_generator.received_indicators is indicators
    assert (
        "Auditoría Stoch snapshot: "
        "visibles=2 | OHLC cerradas=1 | "
        "K-periodo=5 | geometría=1/1 | "
        "consistencia=OK" in result.reason
    )
    assert (
        "Auditoría Stoch OHLC: "
        "máximo=120.00 | mínimo=80.00 | "
        "cierre=104.00 | rango=40.00" in result.reason
    )
    assert (
        "Auditoría Stoch cálculo: "
        "K bruto=60.00 | K suavizado=24.00 | D=21.00" in result.reason
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
    assert "Not enough visual candles to calculate indicators." in result.reason
    assert "Minimum visible required: 14." in result.reason
    assert "Minimum closed required: 13." in result.reason


def test_audit_does_not_mix_current_capture_with_cached_context() -> None:

    original_series = _visual_series()

    current_series = CandleSeries(
        candles=(
            *original_series.candles,
            ClassifiedCandle(
                candidate=CandleCandidate(
                    x=30,
                    y=30,
                    width=5,
                    height=20,
                    area=100,
                    geometry=CandleGeometry(
                        high_y=30,
                        body_top_y=35,
                        body_bottom_y=44,
                        low_y=49,
                    ),
                ),
                candle_type=CandleType.BULLISH,
            ),
        ),
    )

    analysis = MarketAnalysis(
        series=current_series,
        trend=TrendDirection.BULLISH,
    )

    pipeline = VisualStrategySignalAnalysisPipeline(
        market_analysis_pipeline=FakeMarketAnalysisPipeline(
            result=analysis,
        ),
        indicator_snapshot_builder=(
            FakeVisualIndicatorSnapshotBuilder(
                result=_indicators(),
                snapshot_context=(
                    VisualIndicatorSnapshotContext(
                        visible_candle_count=2,
                        ohlc_candle_count=1,
                        geometry_valid_count=1,
                        geometry_total_count=1,
                    )
                ),
            )
        ),
        signal_generator=FakeStrategySignalGenerator(
            result=MarketSignal.neutral(
                reason="Waiting.",
            ),
        ),
        profile=StrategyProfile.otc_precision_10s(),
    )

    result = pipeline.analyze(
        image=np.zeros(
            (100, 100, 3),
            dtype=np.uint8,
        ),
    )

    assert "Velas detectadas: 3" in result.reason

    assert "Auditoría Stoch snapshot: visibles=2 | OHLC cerradas=1" in result.reason

    assert "Auditoría Stoch snapshot: visibles=3" not in result.reason


def _timing_status(
    requested_second: int,
    cached_second: int,
    is_settling: bool,
) -> CandleIntervalIndicatorCacheStatus:

    requested_key = CandleIntervalKey(
        started_at=datetime(
            2026,
            7,
            31,
            11,
            9,
            requested_second,
        ),
        duration_seconds=30,
    )

    cached_key = CandleIntervalKey(
        started_at=datetime(
            2026,
            7,
            31,
            11,
            9,
            cached_second,
        ),
        duration_seconds=30,
    )

    return CandleIntervalIndicatorCacheStatus(
        requested_key=requested_key,
        cached_key=cached_key,
        has_snapshot=True,
        is_current=False,
        is_settling=is_settling,
    )


def test_analyze_blocks_actionable_signal_while_snapshot_is_settling() -> None:

    signal_generator = FakeStrategySignalGenerator(
        result=MarketSignal(
            direction=SignalDirection.PUT,
            strength=SignalStrength.HIGH,
            reason="Should not be emitted.",
        ),
    )

    pipeline = VisualStrategySignalAnalysisPipeline(
        market_analysis_pipeline=FakeMarketAnalysisPipeline(
            result=_market_analysis(),
        ),
        indicator_snapshot_builder=(
            FakeVisualIndicatorSnapshotBuilder(
                result=_indicators(),
                snapshot_context=(
                    VisualIndicatorSnapshotContext(
                        visible_candle_count=2,
                        ohlc_candle_count=1,
                        geometry_valid_count=1,
                        geometry_total_count=1,
                    )
                ),
                snapshot_timing_status=_timing_status(
                    requested_second=30,
                    cached_second=0,
                    is_settling=True,
                ),
            )
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
    assert signal_generator.was_called is False
    assert "ESPERANDO_SNAPSHOT_NUEVO" in result.reason
    assert "intervalo solicitado=11:09:30" in result.reason
    assert "intervalo almacenado=11:09:00" in result.reason
    assert "estado=ESTABILIZANDO" in result.reason
    assert "Entrada: ESPERAR" in result.reason


def test_analyze_blocks_actionable_signal_when_snapshot_is_outdated() -> None:

    signal_generator = FakeStrategySignalGenerator(
        result=MarketSignal(
            direction=SignalDirection.CALL,
            strength=SignalStrength.HIGH,
            reason="Should not be emitted.",
        ),
    )

    pipeline = VisualStrategySignalAnalysisPipeline(
        market_analysis_pipeline=FakeMarketAnalysisPipeline(
            result=_market_analysis(),
        ),
        indicator_snapshot_builder=(
            FakeVisualIndicatorSnapshotBuilder(
                result=_indicators(),
                snapshot_context=(
                    VisualIndicatorSnapshotContext(
                        visible_candle_count=2,
                        ohlc_candle_count=1,
                        geometry_valid_count=1,
                        geometry_total_count=1,
                    )
                ),
                snapshot_timing_status=_timing_status(
                    requested_second=30,
                    cached_second=0,
                    is_settling=False,
                ),
            )
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
    assert signal_generator.was_called is False
    assert "estado=DESACTUALIZADO" in result.reason
    assert "Estado: esperando snapshot nuevo" in result.reason


def test_visual_diagnostics_include_candle_filter_stages() -> None:

    base_analysis = _market_analysis()

    analysis = MarketAnalysis(
        series=base_analysis.series,
        trend=base_analysis.trend,
        detection_diagnostics=CandleFilterDiagnostics(
            input_count=23,
            dimension_valid_count=19,
            width_valid_count=12,
            merged_count=12,
            returned_count=12,
            dominant_width=34.0,
        ),
    )

    pipeline = VisualStrategySignalAnalysisPipeline(
        market_analysis_pipeline=FakeMarketAnalysisPipeline(
            result=analysis,
        ),
        indicator_snapshot_builder=FakeVisualIndicatorSnapshotBuilder(
            result=_indicators(),
        ),
        signal_generator=FakeStrategySignalGenerator(
            result=MarketSignal.neutral(
                reason="Waiting.",
            ),
        ),
        profile=StrategyProfile.otc_precision_10s(),
    )

    result = pipeline.analyze(
        image=np.zeros(
            (100, 100, 3),
            dtype=np.uint8,
        ),
    )

    assert (
        "Detección: "
        "segmentados=23 | "
        "dimensiones=19 | "
        "ancho=12 | "
        "fusionados=12 | "
        "devueltos=12" in result.reason
    )

    assert (
        "Reducción detección: "
        "dimensiones=4 | "
        "ancho=7 | "
        "fragmentos fusionados=0 | "
        "límite=0" in result.reason
    )

    assert "Ancho dominante: 34.00 px" in result.reason


def test_analyze_propagates_price_image_and_keeps_strategy_audit() -> None:
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    price_observation_image = np.zeros((20, 100, 3), dtype=np.uint8)
    market_pipeline = FakeMarketAnalysisPipeline(result=_market_analysis())
    pipeline = VisualStrategySignalAnalysisPipeline(
        market_analysis_pipeline=market_pipeline,
        indicator_snapshot_builder=FakeVisualIndicatorSnapshotBuilder(result=None),
        signal_generator=FakeStrategySignalGenerator(
            result=MarketSignal.neutral(reason="Waiting.")
        ),
        profile=StrategyProfile.otc_precision_10s(),
    )

    pipeline.analyze(
        image=image,
        price_observation_image=price_observation_image,
    )

    assert market_pipeline.received_image is image
    assert market_pipeline.received_price_observation_image is (
        price_observation_image
    )
    profile = StrategyProfile.otc_precision_10s()
    generator = StrategySignalGenerator(
        profile=profile,
        evaluator=StrategyConditionEvaluator(),
    )
    pipeline = VisualStrategySignalAnalysisPipeline(
        market_analysis_pipeline=FakeMarketAnalysisPipeline(
            result=_market_analysis(),
        ),
        indicator_snapshot_builder=FakeVisualIndicatorSnapshotBuilder(
            result=_indicators(),
        ),
        signal_generator=generator,
        profile=profile,
    )

    result = pipeline.analyze(image=np.zeros((100, 100, 3), dtype=np.uint8))

    audit = generator.last_condition_audit
    assert audit is not None
    assert result.direction is SignalDirection.CALL
    assert f"CALL: {audit.call.passed_count}/7" in result.reason
    assert f"PUT: {audit.put.passed_count}/7" in result.reason
    assert "✅ Tendencia" in result.reason
    assert "❌ Tendencia — BLOQUEA" in result.reason
    assert result.reason.count("— BLOQUEA") == len(audit.put.failures)


def test_strategy_diagnostics_are_optional_for_compatible_fakes() -> None:
    pipeline = VisualStrategySignalAnalysisPipeline(
        market_analysis_pipeline=FakeMarketAnalysisPipeline(
            result=_market_analysis(),
        ),
        indicator_snapshot_builder=FakeVisualIndicatorSnapshotBuilder(
            result=_indicators(),
        ),
        signal_generator=FakeStrategySignalGenerator(
            result=MarketSignal.neutral(reason="Waiting."),
        ),
        profile=StrategyProfile.otc_precision_10s(),
    )

    result = pipeline.analyze(image=np.zeros((100, 100, 3), dtype=np.uint8))

    assert result.direction is SignalDirection.NONE
    assert "[strategy_diagnostics]" not in result.reason


def test_build_last_observation_preserves_current_visual_price_identity() -> None:
    instant = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)
    key = CandleIntervalKey(started_at=instant, duration_seconds=30)
    extraction = CurrentVisualPriceExtraction(
        price=CurrentVisualPrice(514.0, 0.73125, 1320, 800, "test", 0.92),
        status=CurrentVisualPriceStatus.OK,
        candidate_count=1,
        selected_x=1268.5,
        selected_y=514.0,
        confidence=0.92,
    )
    analysis = MarketAnalysis(
        series=_visual_series(),
        trend=TrendDirection.BULLISH,
        current_visual_price=extraction,
    )
    profile = StrategyProfile.otc_precision_10s()
    pipeline = VisualStrategySignalAnalysisPipeline(
        market_analysis_pipeline=FakeMarketAnalysisPipeline(result=analysis),
        indicator_snapshot_builder=FakeVisualIndicatorSnapshotBuilder(
            result=_indicators(),
            snapshot_timing_status=CandleIntervalIndicatorCacheStatus(
                requested_key=key,
                cached_key=key,
                has_snapshot=True,
                is_current=True,
                is_settling=False,
            ),
        ),
        signal_generator=StrategySignalGenerator(
            profile=profile,
            evaluator=StrategyConditionEvaluator(),
        ),
        profile=profile,
    )

    pipeline.analyze(image=np.zeros((100, 100, 3), dtype=np.uint8))
    observation = pipeline.build_last_observation(instant)

    assert observation is not None
    assert observation.current_visual_price is extraction
