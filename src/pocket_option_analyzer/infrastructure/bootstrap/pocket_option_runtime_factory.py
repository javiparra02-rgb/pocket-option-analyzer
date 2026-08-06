from __future__ import annotations

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
from pocket_option_analyzer.infrastructure.capture.errors import (
    CaptureUnavailableError,
)
from pocket_option_analyzer.infrastructure.capture.services import (
    CaptureService,
    FrameBuffer,
    FrameFactory,
    RuntimeRoiDebugCapture,
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


@dataclass(frozen=True, slots=True)
class RuntimeWindowHandle:
    """
    Ventana localizada por el runtime.

    Solo las ventanas visibles, no minimizadas y con geometría positiva
    son candidatas válidas para captura.
    """

    hwnd: int

    title: str

    left: int = 0

    top: int = 0

    width: int = 0

    height: int = 0

    visible: bool = True

    minimized: bool = False

    @property
    def area(
        self,
    ) -> int:
        return self.width * self.height

    @property
    def is_capture_candidate(
        self,
    ) -> bool:
        return (
            self.hwnd > 0
            and bool(
                self.title.strip(),
            )
            and self.visible
            and not self.minimized
            and self.width > 0
            and self.height > 0
        )


@dataclass(frozen=True, slots=True)
class RuntimeWindowInfo:
    """
    Información completa de una ventana para captura con MSS.

    Las coordenadas pueden ser negativas cuando la ventana está
    situada en un monitor secundario.
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
    def right(
        self,
    ) -> int:
        return self.left + self.width

    @property
    def bottom(
        self,
    ) -> int:
        return self.top + self.height

    @property
    def area(
        self,
    ) -> int:
        return self.width * self.height

    @property
    def is_capture_candidate(
        self,
    ) -> bool:
        return (
            self.hwnd > 0
            and bool(
                self.title.strip(),
            )
            and self.visible
            and not self.minimized
            and self.width > 0
            and self.height > 0
        )


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
        Devuelve la ventana capturable más grande cuyo título coincida.

        La selección se realiza en una sola pasada y no mantiene una
        colección adicional de coincidencias.
        """

        search = title.strip().casefold()

        if not search:
            return None

        return max(
            (
                window
                for window in self._window_provider()
                if (window.is_capture_candidate and search in window.title.casefold())
            ),
            key=lambda window: window.area,
            default=None,
        )

    def _enumerate_windows(
        self,
    ) -> Iterable[RuntimeWindowHandle]:
        """
        Enumera ventanas Win32 aptas para evaluación de captura.
        """

        windows: list[RuntimeWindowHandle] = []

        user32 = ctypes.windll.user32

        enum_windows_proc = ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HWND,
            wintypes.LPARAM,
        )

        def callback(
            hwnd,
            lparam,
        ) -> bool:
            del lparam

            if not user32.IsWindowVisible(
                hwnd,
            ):
                return True

            if user32.IsIconic(
                hwnd,
            ):
                return True

            title_length = user32.GetWindowTextLengthW(
                hwnd,
            )

            if title_length <= 0:
                return True

            title_buffer = ctypes.create_unicode_buffer(
                title_length + 1,
            )

            copied_length = user32.GetWindowTextW(
                hwnd,
                title_buffer,
                title_length + 1,
            )

            if copied_length <= 0:
                return True

            title = title_buffer.value.strip()

            if not title:
                return True

            rect = wintypes.RECT()

            if not user32.GetWindowRect(
                hwnd,
                ctypes.byref(
                    rect,
                ),
            ):
                return True

            width = rect.right - rect.left
            height = rect.bottom - rect.top

            if width <= 0 or height <= 0:
                return True

            windows.append(
                RuntimeWindowHandle(
                    hwnd=int(
                        hwnd,
                    ),
                    title=title,
                    left=rect.left,
                    top=rect.top,
                    width=width,
                    height=height,
                    visible=True,
                    minimized=False,
                )
            )

            return True

        callback_reference = enum_windows_proc(
            callback,
        )

        enumeration_succeeded = user32.EnumWindows(
            callback_reference,
            0,
        )

        if not enumeration_succeeded:
            raise RuntimeError("Could not enumerate Win32 windows.")

        return windows


class RuntimeWindowReader:
    """
    Lee y valida la ventana localizada inmediatamente antes de capturarla.

    La validación permite detectar cuando la ventana desaparece, se
    minimiza o deja de ser capturable entre find() y read().
    """

    def __init__(
        self,
        info_provider: WindowInfoProvider | None = None,
    ) -> None:
        self._info_provider = (
            info_provider if info_provider is not None else self._read_window_info
        )

    def read(
        self,
        hwnd: int,
    ) -> RuntimeWindowInfo:
        if hwnd <= 0:
            raise ValueError("Window handle must be greater than zero.")

        window = self._info_provider(
            hwnd,
        )

        if window.hwnd != hwnd:
            raise RuntimeError(
                "Window reader returned an unexpected handle: "
                f"requested={hwnd}, returned={window.hwnd}."
            )

        if not window.is_capture_candidate:
            raise CaptureUnavailableError(
                f"Window is not available for capture: hwnd={hwnd}."
            )

        return window

    def _read_window_info(
        self,
        hwnd: int,
    ) -> RuntimeWindowInfo:
        user32 = ctypes.windll.user32

        if not user32.IsWindow(
            hwnd,
        ):
            raise CaptureUnavailableError(f"Window no longer exists: hwnd={hwnd}.")

        visible = bool(
            user32.IsWindowVisible(
                hwnd,
            )
        )

        minimized = bool(
            user32.IsIconic(
                hwnd,
            )
        )

        if not visible or minimized:
            raise CaptureUnavailableError(
                f"Window is not available for capture: hwnd={hwnd}."
            )

        rect = wintypes.RECT()

        rectangle_succeeded = user32.GetWindowRect(
            hwnd,
            ctypes.byref(
                rect,
            ),
        )

        if not rectangle_succeeded:
            raise CaptureUnavailableError(
                f"Could not read window rectangle for hwnd: {hwnd}."
            )

        width = rect.right - rect.left
        height = rect.bottom - rect.top

        if width <= 0 or height <= 0:
            raise CaptureUnavailableError(
                f"Window has invalid capture geometry: hwnd={hwnd}."
            )

        title_length = user32.GetWindowTextLengthW(
            hwnd,
        )

        if title_length <= 0:
            raise CaptureUnavailableError(
                f"Could not read window title for hwnd: {hwnd}."
            )

        title_buffer = ctypes.create_unicode_buffer(
            title_length + 1,
        )

        copied_length = user32.GetWindowTextW(
            hwnd,
            title_buffer,
            title_length + 1,
        )

        if copied_length <= 0:
            raise CaptureUnavailableError(
                f"Could not read window title for hwnd: {hwnd}."
            )

        title = title_buffer.value.strip()

        if not title:
            raise CaptureUnavailableError(f"Window title is empty for hwnd: {hwnd}.")

        return RuntimeWindowInfo(
            hwnd=hwnd,
            title=title,
            left=rect.left,
            top=rect.top,
            width=width,
            height=height,
            visible=visible,
            minimized=minimized,
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
