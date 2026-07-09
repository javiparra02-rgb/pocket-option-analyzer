from __future__ import annotations

from datetime import datetime, timezone

import cv2
import numpy as np

import ctypes
from collections.abc import Callable, Iterable
from ctypes import wintypes
from dataclasses import dataclass
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
)
from pocket_option_analyzer.vision.models import (
    CandleColorProfile,
    ChartRegion,
)


@dataclass(frozen=True, slots=True)
class RuntimeWindowHandle:
    """
    Ventana localizada por el runtime.
    """

    hwnd: int

    title: str

    left: int = 0

    top: int = 0

    width: int = 0

    height: int = 0


@dataclass(frozen=True, slots=True)
class RuntimeWindowInfo:
    """
    Información completa de ventana para captura con MSS.
    """

    hwnd: int

    title: str

    left: int

    top: int

    width: int

    height: int

    visible: bool = True

    minimized: bool = False

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height


WindowProvider = Callable[[], Iterable[RuntimeWindowHandle]]
WindowInfoProvider = Callable[[int], RuntimeWindowInfo]


class RuntimeWindowFinder:
    """
    Localizador de ventanas usado por el runtime real.
    """

    def __init__(
        self,
        window_provider: WindowProvider | None = None,
    ) -> None:
        self._window_provider = window_provider or self._enumerate_windows

    def find(
        self,
        title: str,
    ) -> RuntimeWindowHandle | None:
        """
        Busca la mejor ventana cuyo título contenga el texto indicado.
        """

        search = title.lower()

        matches = [
            window
            for window in self._window_provider()
            if search in window.title.lower()
        ]

        if not matches:
            return None

        matches.sort(
            key=lambda window: window.width * window.height,
            reverse=True,
        )

        return matches[0]

    def _enumerate_windows(
        self,
    ) -> Iterable[RuntimeWindowHandle]:
        """
        Enumera ventanas visibles usando Win32 directamente.
        """

        windows: list[RuntimeWindowHandle] = []

        enum_windows_proc = ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HWND,
            wintypes.LPARAM,
        )

        def callback(
            hwnd,
            lparam,
        ) -> bool:
            if not ctypes.windll.user32.IsWindowVisible(hwnd):
                return True

            title_length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)

            if title_length <= 0:
                return True

            title_buffer = ctypes.create_unicode_buffer(
                title_length + 1,
            )

            ctypes.windll.user32.GetWindowTextW(
                hwnd,
                title_buffer,
                title_length + 1,
            )

            title = title_buffer.value

            rect = wintypes.RECT()

            if not ctypes.windll.user32.GetWindowRect(
                hwnd,
                ctypes.byref(rect),
            ):
                return True

            windows.append(
                RuntimeWindowHandle(
                    hwnd=int(hwnd),
                    title=title,
                    left=rect.left,
                    top=rect.top,
                    width=rect.right - rect.left,
                    height=rect.bottom - rect.top,
                )
            )

            return True

        ctypes.windll.user32.EnumWindows(
            enum_windows_proc(callback),
            0,
        )

        return windows


class RuntimeWindowReader:
    """
    Reader simple para el runtime real.
    """

    def __init__(
        self,
        info_provider: WindowInfoProvider | None = None,
    ) -> None:
        self._info_provider = info_provider or self._read_window_info

    def read(
        self,
        hwnd: int,
    ) -> RuntimeWindowInfo:
        return self._info_provider(
            hwnd,
        )

    def _read_window_info(
        self,
        hwnd: int,
    ) -> RuntimeWindowInfo:
        rect = wintypes.RECT()

        success = ctypes.windll.user32.GetWindowRect(
            hwnd,
            ctypes.byref(rect),
        )

        if not success:
            raise RuntimeError(
                f"Could not read window rectangle for hwnd: {hwnd}"
            )

        title_buffer = ctypes.create_unicode_buffer(
            512,
        )

        ctypes.windll.user32.GetWindowTextW(
            hwnd,
            title_buffer,
            512,
        )

        return RuntimeWindowInfo(
            hwnd=hwnd,
            title=title_buffer.value,
            left=rect.left,
            top=rect.top,
            width=rect.right - rect.left,
            height=rect.bottom - rect.top,
            visible=bool(
                ctypes.windll.user32.IsWindowVisible(
                    hwnd,
                )
            ),
            minimized=bool(
                ctypes.windll.user32.IsIconic(
                    hwnd,
                )
            ),
        )


class FixedChartRegionExtractor:
    """
    Extractor de región fija para el gráfico.
    """

    def __init__(
        self,
        region: ChartRegion,
    ) -> None:
        self._region = region

    def extract(
        self,
        image,
    ) -> ChartRegion:
        return self._clamp_region(
            image=image,
            region=self._region,
        )

    def _clamp_region(
        self,
        image,
        region: ChartRegion,
    ) -> ChartRegion:
        image_height = image.shape[0]
        image_width = image.shape[1]

        x = max(
            0,
            min(
                region.x,
                image_width,
            ),
        )
        y = max(
            0,
            min(
                region.y,
                image_height,
            ),
        )

        width = max(
            0,
            min(
                region.width,
                image_width - x,
            ),
        )
        height = max(
            0,
            min(
                region.height,
                image_height - y,
            ),
        )

        return ChartRegion(
            x=x,
            y=y,
            width=width,
            height=height,
        )


class PocketOptionChartRegionExtractor:
    """
    Extractor proporcional para el gráfico principal de Pocket Option.

    Excluye aproximadamente:
    - barra superior
    - una pequeña parte del panel derecho
    - zona inferior no esencial

    El objetivo es capturar más contexto del gráfico sin incluir
    demasiado panel lateral.
    """

    def __init__(
        self,
        top_ratio: float = 0.07,
        right_ratio: float = 0.06,
        bottom_ratio: float = 0.14,
    ) -> None:
        self._top_ratio = top_ratio
        self._right_ratio = right_ratio
        self._bottom_ratio = bottom_ratio

    def extract(
        self,
        image,
    ) -> ChartRegion:
        image_height = image.shape[0]
        image_width = image.shape[1]

        x = 0
        y = int(
            image_height * self._top_ratio,
        )

        right_margin = int(
            image_width * self._right_ratio,
        )
        bottom_margin = int(
            image_height * self._bottom_ratio,
        )

        width = image_width - right_margin
        height = image_height - y - bottom_margin

        return ChartRegion(
            x=x,
            y=y,
            width=max(
                0,
                width,
            ),
            height=max(
                0,
                height,
            ),
        )


class RuntimeRoiDebugCapture:
    """
    Guarda el ROI real que será analizado por el sistema.

    Esto permite depurar:
    - si el recorte del gráfico es correcto
    - si las velas llegan visibles al detector
    - si la GUI está tapando parte del gráfico
    """

    def __init__(
        self,
        directory: Path = Path("debug") / "runtime_roi",
        filename_prefix: str = "roi",
    ) -> None:
        self._directory = directory
        self._filename_prefix = filename_prefix
        self._latest_path: Path | None = None

    @property
    def latest_path(self) -> Path | None:
        return self._latest_path

    def save(
        self,
        image: np.ndarray,
    ) -> None:
        self._directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        timestamp = datetime.now(
            tz=timezone.utc,
        ).strftime(
            "%Y%m%d_%H%M%S_%f",
        )

        file_path = self._directory / f"{self._filename_prefix}_{timestamp}.png"

        success = cv2.imwrite(
            str(file_path),
            image,
        )

        if not success:
            raise RuntimeError(
                f"Could not save runtime ROI debug image: {file_path}"
            )

        self._latest_path = file_path


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

    @staticmethod
    def create_runtime_service(
        capture_service: FrameCaptureService | None = None,
        signal_history: SignalHistory | None = None,
        signal_file_path: Path | None = DEFAULT_SIGNAL_FILE_PATH,
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

        finder = RuntimeWindowFinder()
        reader = RuntimeWindowReader()

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
            finder=finder,
            reader=reader,
            capture=MSSCaptureAdapter(),
            region_extractor=region_extractor,
            frame_factory=FrameFactory(),
            frame_buffer=FrameBuffer(
                max_size=20,
            ),
            dataset_capture=dataset_capture,
            window_title=window_title,
        )