from __future__ import annotations

from pathlib import Path
from typing import Any

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
    Win32WindowLocator,
)
from pocket_option_analyzer.infrastructure.capture.services import (
    CaptureService,
    FrameBuffer,
    FrameFactory,
)
from pocket_option_analyzer.vision.models import (
    CandleColorProfile,
    ChartRegion,
)


class WindowLocatorReaderAdapter:
    """
    Adapta un WindowLocator existente al contrato esperado por CaptureService.

    CaptureService espera un objeto con método:
    - read(window_title)

    Win32WindowLocator puede exponer el método con otro nombre según la capa
    de infraestructura. Este adaptador evita acoplar el runtime a esos detalles.
    """

    def __init__(
        self,
        locator: Any,
    ) -> None:
        self._locator = locator

    def read(
        self,
        window_title: str,
    ):
        """
        Lee/localiza una ventana usando el localizador interno.
        """

        for method_name in (
            "read",
            "locate",
            "find",
            "find_by_title",
            "find_window",
        ):
            method = getattr(
                self._locator,
                method_name,
                None,
            )

            if callable(method):
                return method(
                    window_title,
                )

        raise AttributeError(
            "Window locator does not expose a compatible read method."
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

    DEFAULT_SIGNAL_FILE_PATH = Path(
        "logs",
    ) / "signals.jsonl"

    DEFAULT_CHART_REGION = ChartRegion(
        x=0,
        y=0,
        width=1550,
        height=848,
    )

    @staticmethod
    def create_runtime_service(
        capture_service: FrameCaptureService | None = None,
        signal_history: SignalHistory | None = None,
        signal_file_path: Path | None = DEFAULT_SIGNAL_FILE_PATH,
        strategy_profile: StrategyProfile | None = None,
        color_profile: CandleColorProfile | None = None,
        window_title: str = DEFAULT_WINDOW_TITLE,
        chart_region: ChartRegion | None = DEFAULT_CHART_REGION,
        interval_seconds: float = 1.0,
    ) -> AnalysisRuntimeService:
        """
        Crea el runtime principal para la GUI.

        Si capture_service no se entrega, crea un CaptureService real
        configurado para buscar la ventana de Pocket Option.
        """

        resolved_capture_service = (
            capture_service
            if capture_service is not None
            else PocketOptionRuntimeFactory.create_capture_service(
                window_title=window_title,
                chart_region=chart_region,
            )
        )

        return SignalPipelineFactory.create_analysis_runtime_service(
            capture_service=resolved_capture_service,
            signal_history=signal_history,
            signal_file_path=signal_file_path,
            strategy_profile=strategy_profile,
            color_profile=color_profile,
            interval_seconds=interval_seconds,
        )

    @staticmethod
    def create_capture_service(
        window_title: str = DEFAULT_WINDOW_TITLE,
        chart_region: ChartRegion | None = DEFAULT_CHART_REGION,
    ) -> CaptureService:
        """
        Crea el servicio real de captura para Pocket Option.

        Orden actual esperado por CaptureService:
        - window_title
        - window_reader compatible con read()
        - capture_adapter
        - chart_region
        - frame_factory
        - frame_buffer
        """

        resolved_chart_region = (
            chart_region
            if chart_region is not None
            else PocketOptionRuntimeFactory.DEFAULT_CHART_REGION
        )

        return CaptureService(
            window_title,
            WindowLocatorReaderAdapter(
                Win32WindowLocator(),
            ),
            MSSCaptureAdapter(),
            resolved_chart_region,
            FrameFactory(),
            FrameBuffer(
                max_size=20,
            ),
        )