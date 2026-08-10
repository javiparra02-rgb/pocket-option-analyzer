from __future__ import annotations

from pathlib import Path

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
    ) -> AnalysisRuntimeService:
        """
        Crea el runtime principal para la GUI.
        """

        resolved_capture_service = (
            capture_service
            if capture_service is not None
            else PocketOptionRuntimeFactory.create_capture_service(
                window_title=window_title,
                chart_region=chart_region,
                debug_roi_directory=debug_roi_directory,
            )
        )

        resolved_color_profile = (
            color_profile
            if color_profile is not None
            else CandleColorProfile.white_red()
        )

        return SignalPipelineFactory.create_analysis_runtime_service(
            capture_service=resolved_capture_service,
            signal_history=signal_history,
            signal_file_path=signal_file_path,
            observation_file_path=observation_file_path,
            strategy_profile=strategy_profile,
            color_profile=resolved_color_profile,
            interval_seconds=interval_seconds,
        )

    @staticmethod
    def create_capture_service(
        window_title: str = DEFAULT_WINDOW_TITLE,
        chart_region: ChartRegion | None = None,
        debug_roi_directory: Path | None = None,
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
            price_observation_region_extractor=(
                PocketOptionPriceObservationRegionExtractor(
                    bottom_extension_ratio=0.0,
                )
            ),
        )
