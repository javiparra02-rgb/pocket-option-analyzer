from __future__ import annotations

from pathlib import Path

from pocket_option_analyzer.application.market import (
    VisualIndicatorSnapshotBuilder,
)
from pocket_option_analyzer.application.signals import (
    SignalRecorder,
    SignalRecordingPipeline,
    StrategySignalAnalysisPipeline,
    StrategySignalGenerator,
    VisualSignalRecordingPipeline,
    VisualStrategySignalAnalysisPipeline,
)
from pocket_option_analyzer.application.strategy import (
    StrategyConditionEvaluator,
)
from pocket_option_analyzer.domain.signals import SignalHistory
from pocket_option_analyzer.domain.strategy import StrategyProfile
from pocket_option_analyzer.infrastructure.signals import (
    JsonlSignalRecordWriter,
)
from pocket_option_analyzer.vision.models import CandleColorProfile
from pocket_option_analyzer.vision.services import (
    BinaryMaskBuilder,
    CandleAnalysisPipeline,
    CandleClassificationPipeline,
    CandleClassifier,
    CandleColorDetector,
    CandleDetectionPipeline,
    CandleFilter,
    CandleSegmenter,
    CandleSeriesBuilder,
    MarketAnalysisPipeline,
    TrendDetector,
)


class SignalPipelineFactory:
    """
    Ensambla pipelines completos de análisis y registro de señales.

    Esta clase pertenece a infrastructure porque conecta implementaciones
    concretas con contratos de application.

    No ejecuta operaciones.
    No interactúa con Pocket Option.
    Solo construye objetos para analizar, generar y registrar señales.
    """

    @staticmethod
    def create_signal_recording_pipeline(
        signal_history: SignalHistory | None = None,
        signal_file_path: Path | None = None,
        strategy_profile: StrategyProfile | None = None,
        color_profile: CandleColorProfile | None = None,
    ) -> SignalRecordingPipeline:
        """
        Crea el pipeline clásico de señales.

        Este pipeline requiere:
        - imagen
        - indicadores externos ya calculados
        """

        history = signal_history or SignalHistory()
        profile = strategy_profile or StrategyProfile.otc_precision_10s()

        market_analysis_pipeline = (
            SignalPipelineFactory._create_market_analysis_pipeline(
                color_profile=color_profile,
            )
        )

        strategy_signal_generator = (
            SignalPipelineFactory._create_strategy_signal_generator(
                profile=profile,
            )
        )

        strategy_signal_analysis_pipeline = StrategySignalAnalysisPipeline(
            market_analysis_pipeline=market_analysis_pipeline,
            signal_generator=strategy_signal_generator,
        )

        recorder = SignalRecorder(
            history=history,
        )

        writer = SignalPipelineFactory._create_signal_record_writer(
            signal_file_path=signal_file_path,
        )

        return SignalRecordingPipeline(
            analysis_pipeline=strategy_signal_analysis_pipeline,
            recorder=recorder,
            record_writer=writer,
        )

    @staticmethod
    def create_visual_signal_recording_pipeline(
        signal_history: SignalHistory | None = None,
        signal_file_path: Path | None = None,
        strategy_profile: StrategyProfile | None = None,
        color_profile: CandleColorProfile | None = None,
    ) -> VisualSignalRecordingPipeline:
        """
        Crea el pipeline visual completo de señales.

        Este pipeline solo requiere:
        - imagen capturada

        Los indicadores se calculan automáticamente desde las velas visuales.
        """

        history = signal_history or SignalHistory()
        profile = strategy_profile or StrategyProfile.otc_precision_10s()

        market_analysis_pipeline = (
            SignalPipelineFactory._create_market_analysis_pipeline(
                color_profile=color_profile,
            )
        )

        strategy_signal_generator = (
            SignalPipelineFactory._create_strategy_signal_generator(
                profile=profile,
            )
        )

        visual_strategy_signal_analysis_pipeline = (
            VisualStrategySignalAnalysisPipeline(
                market_analysis_pipeline=market_analysis_pipeline,
                indicator_snapshot_builder=VisualIndicatorSnapshotBuilder(),
                signal_generator=strategy_signal_generator,
                profile=profile,
            )
        )

        recorder = SignalRecorder(
            history=history,
        )

        writer = SignalPipelineFactory._create_signal_record_writer(
            signal_file_path=signal_file_path,
        )

        return VisualSignalRecordingPipeline(
            analysis_pipeline=visual_strategy_signal_analysis_pipeline,
            recorder=recorder,
            record_writer=writer,
        )

    @staticmethod
    def _create_market_analysis_pipeline(
        color_profile: CandleColorProfile | None = None,
    ) -> MarketAnalysisPipeline:

        detection_pipeline = CandleDetectionPipeline(
            mask_builder=BinaryMaskBuilder(),
            segmenter=CandleSegmenter(),
            candle_filter=CandleFilter(),
            color_detector=CandleColorDetector(),
        )

        classification_pipeline = CandleClassificationPipeline(
            classifier=CandleClassifier(
                color_profile=color_profile,
            ),
        )

        candle_analysis_pipeline = CandleAnalysisPipeline(
            detection_pipeline=detection_pipeline,
            classification_pipeline=classification_pipeline,
        )

        return MarketAnalysisPipeline(
            candle_analysis_pipeline=candle_analysis_pipeline,
            series_builder=CandleSeriesBuilder(),
            trend_detector=TrendDetector(),
        )

    @staticmethod
    def _create_strategy_signal_generator(
        profile: StrategyProfile,
    ) -> StrategySignalGenerator:

        return StrategySignalGenerator(
            profile=profile,
            evaluator=StrategyConditionEvaluator(),
        )

    @staticmethod
    def _create_signal_record_writer(
        signal_file_path: Path | None,
    ) -> JsonlSignalRecordWriter | None:

        if signal_file_path is None:
            return None

        return JsonlSignalRecordWriter(
            file_path=signal_file_path,
        )