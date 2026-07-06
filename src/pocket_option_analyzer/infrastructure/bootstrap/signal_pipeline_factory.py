from __future__ import annotations

from pathlib import Path

from pocket_option_analyzer.application.signals import (
    SignalRecorder,
    SignalRecordingPipeline,
    StrategySignalAnalysisPipeline,
    StrategySignalGenerator,
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
    Ensambla el pipeline completo de análisis y registro de señales.

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
        Crea el pipeline completo de análisis de señales.

        Parameters
        ----------
        signal_history:
            Historial en memoria donde se registrarán las señales.

        signal_file_path:
            Ruta opcional para persistir señales en formato JSONL.

        strategy_profile:
            Perfil de estrategia. Si no se entrega, usa OTC Precision 10S.

        color_profile:
            Perfil de colores de velas. Si no se entrega, usa green/red.
        """

        history = signal_history or SignalHistory()
        profile = strategy_profile or StrategyProfile.otc_precision_10s()

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

        market_analysis_pipeline = MarketAnalysisPipeline(
            candle_analysis_pipeline=candle_analysis_pipeline,
            series_builder=CandleSeriesBuilder(),
            trend_detector=TrendDetector(),
        )

        strategy_signal_generator = StrategySignalGenerator(
            profile=profile,
            evaluator=StrategyConditionEvaluator(),
        )

        strategy_signal_analysis_pipeline = StrategySignalAnalysisPipeline(
            market_analysis_pipeline=market_analysis_pipeline,
            signal_generator=strategy_signal_generator,
        )

        recorder = SignalRecorder(
            history=history,
        )

        writer = (
            JsonlSignalRecordWriter(
                file_path=signal_file_path,
            )
            if signal_file_path is not None
            else None
        )

        return SignalRecordingPipeline(
            analysis_pipeline=strategy_signal_analysis_pipeline,
            recorder=recorder,
            record_writer=writer,
        )