from __future__ import annotations

from pathlib import Path

from pocket_option_analyzer.application.evidence import (
    IdentityShadowEvidenceConfig,
    IdentityShadowPngMode,
)
from pocket_option_analyzer.application.runtime import (
    AnalysisRuntimeService,
)
from pocket_option_analyzer.application.use_cases import (
    FrameCaptureService,
)
from pocket_option_analyzer.domain.signals import SignalHistory
from pocket_option_analyzer.domain.strategy import StrategyProfile
from pocket_option_analyzer.infrastructure.bootstrap.signal_pipeline_factory import (
    SignalPipelineFactory,
)
from pocket_option_analyzer.infrastructure.capture.adapters import (
    MSSCaptureAdapter,
)
from pocket_option_analyzer.infrastructure.capture.services import (
    CaptureService,
    FrameBuffer,
    FrameFactory,
    RuntimeRoiDebugCapture,
)
from pocket_option_analyzer.infrastructure.config import Settings, get_settings
from pocket_option_analyzer.infrastructure.windows.native import User32
from pocket_option_analyzer.infrastructure.windows.services import (
    WindowEnumerator,
    WindowFactory,
    WindowFinder,
    WindowReader,
)
from pocket_option_analyzer.vision.models import (
    CandleColorProfile,
    ChartRegion,
)
from pocket_option_analyzer.vision.services.fixed_chart_region_extractor import (
    FixedChartRegionExtractor,
)
from pocket_option_analyzer.vision.services.pocket_option_chart_region_extractor import (  # noqa: E501
    PocketOptionChartRegionExtractor,
)
from pocket_option_analyzer.vision.services.pocket_option_price_observation_region_extractor import (  # noqa: E501
    PocketOptionPriceObservationRegionExtractor,
)


class PocketOptionRuntimeFactory:
    """
    Construye el runtime real de análisis para Pocket Option.

    No ejecuta operaciones.
    No hace clic.
    No interactúa con Pocket Option.
    Solo configura captura visual, análisis y registro de señales.
    """

    DEFAULT_WINDOW_TITLE = "Pocket Option"

    DEFAULT_SIGNAL_FILE_PATH = (
        Path(
            "logs",
        )
        / "signals.jsonl"
    )
    DEFAULT_OBSERVATION_FILE_PATH = Path("logs") / "strategy_observations.jsonl"

    @staticmethod
    def create_runtime_service(
        capture_service: FrameCaptureService | None = None,
        signal_history: SignalHistory | None = None,
        signal_file_path: Path | None = DEFAULT_SIGNAL_FILE_PATH,
        observation_file_path: Path | None = DEFAULT_OBSERVATION_FILE_PATH,
        strategy_profile: StrategyProfile | None = None,
        color_profile: CandleColorProfile | None = None,
        window_title: str = DEFAULT_WINDOW_TITLE,
        chart_region: ChartRegion | None = None,
        interval_seconds: float = 1.0,
        debug_roi_directory: Path | None = None,
        settings: Settings | None = None,
    ) -> AnalysisRuntimeService:
        """
        Crea el runtime principal para la GUI.
        """

        resolved_settings = settings if settings is not None else get_settings()
        originals_config = None
        if resolved_settings.observational_evidence_enabled:
            originals_config = resolved_settings.observational_evidence_config
            if originals_config is None:
                raise ValueError(
                    "Observational evidence requires explicit directory and budgets"
                )

        resolved_capture_service = (
            capture_service
            if capture_service is not None
            else PocketOptionRuntimeFactory.create_capture_service(
                window_title=window_title,
                chart_region=chart_region,
                debug_roi_directory=debug_roi_directory,
                observational_evidence_enabled=originals_config is not None,
                instrument_context_region=(
                    ChartRegion(*originals_config.context_region)
                    if originals_config is not None and originals_config.context_region
                    else None
                ),
                observational_frame_byte_limit=(
                    originals_config.max_frame_bytes
                    if originals_config is not None
                    else None
                ),
            )
        )

        resolved_color_profile = (
            color_profile
            if color_profile is not None
            else CandleColorProfile.white_red()
        )

        identity_evidence_config = None
        if resolved_settings.visual_identity_evidence_enabled:
            if resolved_settings.visual_evidence_directory is None:
                raise ValueError(
                    "VISUAL_IDENTITY_EVIDENCE_ENABLED requires "
                    "VISUAL_EVIDENCE_DIRECTORY."
                )
            identity_evidence_config = IdentityShadowEvidenceConfig(
                ring_buffer_size=(
                    resolved_settings.visual_identity_evidence_ring_buffer_size
                ),
                pre_event_trace_count=(
                    resolved_settings.visual_identity_evidence_pre_event_trace_count
                ),
                png_mode=(
                    IdentityShadowPngMode.ALL_FRAMES
                    if resolved_settings.visual_identity_evidence_intensive_png
                    else IdentityShadowPngMode.EVENT_ONLY
                ),
                checkpoint_interval_frames=(
                    resolved_settings.visual_identity_evidence_checkpoint_interval_frames
                ),
            )

        return SignalPipelineFactory.create_analysis_runtime_service(
            capture_service=resolved_capture_service,
            signal_history=signal_history,
            signal_file_path=signal_file_path,
            observation_file_path=observation_file_path,
            strategy_profile=strategy_profile,
            color_profile=resolved_color_profile,
            interval_seconds=interval_seconds,
            visual_evidence_directory=(
                resolved_settings.visual_evidence_directory
            ),
            application_version=resolved_settings.app_version,
            identity_evidence_config=identity_evidence_config,
            observational_evidence_config=originals_config,
        )

    @staticmethod
    def create_capture_service(
        window_title: str = DEFAULT_WINDOW_TITLE,
        chart_region: ChartRegion | None = None,
        debug_roi_directory: Path | None = None,
        observational_evidence_enabled: bool = False,
        instrument_context_region: ChartRegion | None = None,
        observational_frame_byte_limit: int | None = None,
    ) -> CaptureService:
        """
        Crea el servicio real de captura para Pocket Option.
        """

        user32 = User32()

        window_reader = WindowReader(
            user32=user32,
            factory=WindowFactory(),
        )

        window_finder = WindowFinder(
            enumerator=WindowEnumerator(
                user32=user32,
            ),
            reader=window_reader,
        )

        region_extractor = (
            FixedChartRegionExtractor(
                region=chart_region,
            )
            if chart_region is not None
            else PocketOptionChartRegionExtractor()
        )

        dataset_capture = (
            RuntimeRoiDebugCapture(
                directory=debug_roi_directory,
            )
            if debug_roi_directory is not None
            else None
        )

        return CaptureService(
            finder=window_finder,
            reader=window_reader,
            capture=MSSCaptureAdapter(),
            region_extractor=region_extractor,
            frame_factory=FrameFactory(),
            frame_buffer=FrameBuffer(
                max_size=20,
            ),
            dataset_capture=dataset_capture,
            window_title=window_title,
            observational_evidence_enabled=observational_evidence_enabled,
            instrument_context_region=instrument_context_region,
            observational_frame_byte_limit=observational_frame_byte_limit,
            price_observation_region_extractor=(
                PocketOptionPriceObservationRegionExtractor(
                    bottom_extension_ratio=0.0,
                )
            ),
        )
