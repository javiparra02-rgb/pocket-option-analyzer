from __future__ import annotations

from pathlib import Path

from pocket_option_analyzer.application.market import (
    VisualIndicatorSnapshotBuilder,
)
from pocket_option_analyzer.application.runtime import (
    AnalysisRuntimeService,
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
    StrategyObservationRecorder,
)
from pocket_option_analyzer.application.use_cases import (
    AnalyzeCapturedFrameUseCase,
    FrameAnalysisLoopService,
    FrameCaptureService,
)
from pocket_option_analyzer.domain.signals import SignalHistory
from pocket_option_analyzer.domain.strategy import StrategyProfile
from pocket_option_analyzer.infrastructure.evidence import (
    FilesystemVisualEvidenceRecorder,
)
from pocket_option_analyzer.infrastructure.signals import (
    JsonlSignalRecordWriter,
    JsonlStrategyObservationWriter,
)
from pocket_option_analyzer.vision.models import CandleColorProfile
from pocket_option_analyzer.vision.services import (
    CandleAnalysisPipeline,
    CandleClassificationPipeline,
    CandleClassifier,
    CandleColorDetector,
    CandleDetectionPipeline,
    CandleFilter,
    CandleGeometryExtractor,
    CandleSegmenter,
    CandleSeriesBuilder,
    CandleSeriesMembershipResolver,
    MarketAnalysisPipeline,
    PocketOptionCandleMaskBuilder,
    PocketOptionCurrentVisualPriceExtractor,
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

        history = signal_history if signal_history is not None else SignalHistory()

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
        observation_file_path: Path | None = None,
        strategy_profile: StrategyProfile | None = None,
        color_profile: CandleColorProfile | None = None,
        visual_evidence_directory: Path | None = None,
        application_version: str | None = None,
    ) -> VisualSignalRecordingPipeline:
        """
        Crea el pipeline visual completo de señales.

        Este pipeline solo requiere:
        - imagen capturada

        Los indicadores se calculan automáticamente desde las velas visuales.
        """

        history = signal_history if signal_history is not None else SignalHistory()

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

        visual_strategy_signal_analysis_pipeline = VisualStrategySignalAnalysisPipeline(
            market_analysis_pipeline=market_analysis_pipeline,
            indicator_snapshot_builder=VisualIndicatorSnapshotBuilder(),
            signal_generator=strategy_signal_generator,
            profile=profile,
        )

        recorder = SignalRecorder(
            history=history,
        )

        writer = SignalPipelineFactory._create_signal_record_writer(
            signal_file_path=signal_file_path,
        )

        visual_evidence_recorder = (
            FilesystemVisualEvidenceRecorder(
                directory=visual_evidence_directory,
                application_version=application_version,
                observation_jsonl_path=observation_file_path,
            )
            if visual_evidence_directory is not None
            else None
        )

        return VisualSignalRecordingPipeline(
            analysis_pipeline=visual_strategy_signal_analysis_pipeline,
            recorder=recorder,
            record_writer=writer,
            observation_recorder=StrategyObservationRecorder(
                writer=(
                    JsonlStrategyObservationWriter(observation_file_path)
                    if observation_file_path is not None
                    else None
                ),
            ),
            visual_evidence_recorder=visual_evidence_recorder,
        )

    @staticmethod
    def create_captured_frame_analysis_use_case(
        signal_history: SignalHistory | None = None,
        signal_file_path: Path | None = None,
        observation_file_path: Path | None = None,
        strategy_profile: StrategyProfile | None = None,
        color_profile: CandleColorProfile | None = None,
        source: str = "captured_frame_visual_analysis",
        visual_evidence_directory: Path | None = None,
        application_version: str | None = None,
    ) -> AnalyzeCapturedFrameUseCase:
        """
        Crea el caso de uso completo para analizar frames capturados.
        """

        pipeline = SignalPipelineFactory.create_visual_signal_recording_pipeline(
            signal_history=signal_history,
            signal_file_path=signal_file_path,
            observation_file_path=observation_file_path,
            strategy_profile=strategy_profile,
            color_profile=color_profile,
            visual_evidence_directory=visual_evidence_directory,
            application_version=application_version,
        )

        return AnalyzeCapturedFrameUseCase(
            pipeline=pipeline,
            source=source,
        )

    @staticmethod
    def create_frame_analysis_loop_service(
        capture_service: FrameCaptureService,
        signal_history: SignalHistory | None = None,
        signal_file_path: Path | None = None,
        observation_file_path: Path | None = None,
        strategy_profile: StrategyProfile | None = None,
        color_profile: CandleColorProfile | None = None,
        source: str = "captured_frame_visual_analysis",
        interval_seconds: float = 1.0,
        visual_evidence_directory: Path | None = None,
        application_version: str | None = None,
    ) -> FrameAnalysisLoopService:
        """
        Crea el servicio completo de ciclo continuo.

        Este será el motor lógico que luego podrá controlar la GUI:
        - iniciar análisis
        - detener análisis
        - capturar frame
        - analizar señal
        - registrar resultado
        """

        analysis_use_case = (
            SignalPipelineFactory.create_captured_frame_analysis_use_case(
                signal_history=signal_history,
                signal_file_path=signal_file_path,
                observation_file_path=observation_file_path,
                strategy_profile=strategy_profile,
                color_profile=color_profile,
                source=source,
                visual_evidence_directory=visual_evidence_directory,
                application_version=application_version,
            )
        )

        return FrameAnalysisLoopService(
            capture_service=capture_service,
            analysis_use_case=analysis_use_case,
            interval_seconds=interval_seconds,
        )

    @staticmethod
    def create_analysis_runtime_service(
        capture_service: FrameCaptureService,
        signal_history: SignalHistory | None = None,
        signal_file_path: Path | None = None,
        observation_file_path: Path | None = None,
        strategy_profile: StrategyProfile | None = None,
        color_profile: CandleColorProfile | None = None,
        source: str = "captured_frame_visual_analysis",
        interval_seconds: float = 1.0,
        visual_evidence_directory: Path | None = None,
        application_version: str | None = None,
    ) -> AnalysisRuntimeService:
        """
        Crea el runtime completo de análisis.

        Este será el punto de entrada recomendado para la futura GUI:
        - run_once()
        - start()
        - stop()
        - is_running
        """

        loop_service = SignalPipelineFactory.create_frame_analysis_loop_service(
            capture_service=capture_service,
            signal_history=signal_history,
            signal_file_path=signal_file_path,
            observation_file_path=observation_file_path,
            strategy_profile=strategy_profile,
            color_profile=color_profile,
            source=source,
            interval_seconds=interval_seconds,
            visual_evidence_directory=visual_evidence_directory,
            application_version=application_version,
        )

        return AnalysisRuntimeService(
            loop_service=loop_service,
        )

    @staticmethod
    def _create_market_analysis_pipeline(
        color_profile: CandleColorProfile | None = None,
    ) -> MarketAnalysisPipeline:

        detection_pipeline = CandleDetectionPipeline(
            mask_builder=PocketOptionCandleMaskBuilder(),
            segmenter=CandleSegmenter(),
            candle_filter=CandleFilter(),
            color_detector=CandleColorDetector(),
            geometry_extractor=CandleGeometryExtractor(),
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
            membership_resolver=CandleSeriesMembershipResolver(),
            trend_detector=TrendDetector(),
            current_visual_price_extractor=(
                PocketOptionCurrentVisualPriceExtractor(
                    effective_chart_right_x=1062,
                )
            ),
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
