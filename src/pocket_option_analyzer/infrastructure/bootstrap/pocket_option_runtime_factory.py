from __future__ import annotations

import ctypes
from collections.abc import Callable, Iterable
from ctypes import wintypes
from dataclasses import dataclass
from datetime import UTC, datetime
from math import isfinite
from numbers import Real
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

import cv2
import numpy as np

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
)
from pocket_option_analyzer.vision.models import (
    CandleColorProfile,
    ChartRegion,
)
from pocket_option_analyzer.vision.preprocessing import FrameValidator


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


def _require_valid_chart_region_image(
    image: np.ndarray,
) -> np.ndarray:
    """
    Verifica el contrato visual común de los extractores de región.

    Los extractores aceptan únicamente imágenes uint8 BGR o BGRA con
    dimensiones espaciales positivas.
    """

    if not FrameValidator.validate(
        image,
    ):
        raise ValueError(
            "Chart region extractor requires a valid uint8 BGR or BGRA image."
        )

    return image


class FixedChartRegionExtractor:
    """
    Devuelve una región fija configurada para el gráfico.

    La región no se recorta ni modifica según el tamaño de la imagen.
    CaptureService decide posteriormente si cabe completamente dentro
    del frame actual.
    """

    def __init__(
        self,
        region: ChartRegion,
    ) -> None:
        if region.x < 0 or region.y < 0:
            raise ValueError("Fixed chart region coordinates cannot be negative.")

        if not region.has_positive_area:
            raise ValueError("Fixed chart region dimensions must be greater than zero.")

        self._region = region

    def extract(
        self,
        image: np.ndarray,
    ) -> ChartRegion:
        """
        Devuelve exactamente la región configurada.

        La imagen se valida para mantener el mismo contrato estructural
        que los demás extractores.
        """

        _require_valid_chart_region_image(
            image,
        )

        return self._region


class PocketOptionChartRegionExtractor:
    """
    Extrae principalmente el área de velas de Pocket Option.

    Excluye proporcionalmente:
    - la barra superior del navegador y de Pocket Option;
    - el panel derecho de compra y venta;
    - el RSI, la línea temporal y otros paneles inferiores.

    Los indicadores se calculan internamente, por lo que no es
    necesario incluir los paneles RSI o Stochastic visibles.
    """

    def __init__(
        self,
        top_ratio: float = 0.10,
        right_ratio: float = 0.14,
        bottom_ratio: float = 0.15,
    ) -> None:
        self._top_ratio = self._resolve_ratio(
            name="top_ratio",
            value=top_ratio,
        )
        self._right_ratio = self._resolve_ratio(
            name="right_ratio",
            value=right_ratio,
        )
        self._bottom_ratio = self._resolve_ratio(
            name="bottom_ratio",
            value=bottom_ratio,
        )

        if self._top_ratio + self._bottom_ratio >= 1.0:
            raise ValueError("Top and bottom chart ratios must sum to less than one.")

    def extract(
        self,
        image: np.ndarray,
    ) -> ChartRegion:
        """
        Calcula proporcionalmente el área visual destinada a las velas.
        """

        validated_image = _require_valid_chart_region_image(
            image,
        )

        image_height = int(
            validated_image.shape[0],
        )
        image_width = int(
            validated_image.shape[1],
        )

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

        return ChartRegion(
            x=x,
            y=y,
            width=image_width - right_margin,
            height=image_height - y - bottom_margin,
        )

    @staticmethod
    def _resolve_ratio(
        *,
        name: str,
        value: float,
    ) -> float:
        """
        Normaliza y valida una proporción del extractor.
        """

        if isinstance(
            value,
            bool,
        ) or not isinstance(
            value,
            Real,
        ):
            raise TypeError(f"{name} must be a real number.")

        resolved_value = float(
            value,
        )

        if not isfinite(
            resolved_value,
        ):
            raise ValueError(f"{name} must be finite.")

        if not 0.0 <= resolved_value < 1.0:
            raise ValueError(f"{name} must be in range [0, 1).")

        return resolved_value


RuntimeRoiClock = Callable[[], datetime]
RuntimeRoiTokenFactory = Callable[[], str]
RuntimeRoiImageWriter = Callable[
    [
        str,
        np.ndarray,
    ],
    bool,
]


def _runtime_roi_utc_now() -> datetime:
    return datetime.now(
        tz=UTC,
    )


def _runtime_roi_unique_token() -> str:
    return uuid4().hex


class RuntimeRoiDebugCapture:
    """
    Guarda el ROI real que será analizado por el sistema.

    El directorio mantiene únicamente una cantidad acotada de capturas.
    La imagen definitiva solo aparece después de completar correctamente
    la escritura del archivo temporal.
    """

    DEFAULT_MAX_FILES = 300

    def __init__(
        self,
        directory: Path = Path("debug") / "runtime_roi",
        filename_prefix: str = "roi",
        max_files: int = DEFAULT_MAX_FILES,
        clock: RuntimeRoiClock = _runtime_roi_utc_now,
        token_factory: RuntimeRoiTokenFactory = (_runtime_roi_unique_token),
        image_writer: RuntimeRoiImageWriter = cv2.imwrite,
    ) -> None:
        if max_files < 1:
            raise ValueError("Runtime ROI max files must be greater than zero.")

        self._directory = directory
        self._filename_prefix = filename_prefix
        self._max_files = max_files
        self._clock = clock
        self._token_factory = token_factory
        self._image_writer = image_writer

        self._latest_path: Path | None = None

    @property
    def latest_path(
        self,
    ) -> Path | None:
        return self._latest_path

    @property
    def max_files(
        self,
    ) -> int:
        return self._max_files

    def save(
        self,
        image: np.ndarray,
    ) -> None:
        """
        Guarda el ROI y elimina las capturas más antiguas.

        La escritura utiliza un archivo temporal dentro del mismo
        directorio para evitar publicar imágenes incompletas.
        """

        self._directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        destination = self._directory / self._generate_filename()

        if destination.exists():
            raise FileExistsError(
                f"Runtime ROI debug image already exists: {destination}"
            )

        temporary_path = self._create_temporary_path(
            destination=destination,
        )

        try:
            write_succeeded = self._image_writer(
                str(temporary_path),
                image,
            )

            if not write_succeeded or temporary_path.stat().st_size == 0:
                raise RuntimeError(
                    f"Could not save runtime ROI debug image: {destination}"
                )

            if destination.exists():
                raise FileExistsError(
                    f"Runtime ROI debug image already exists: {destination}"
                )

            temporary_path.replace(
                destination,
            )
        except Exception:
            temporary_path.unlink(
                missing_ok=True,
            )
            raise

        self._latest_path = destination

        self._prune_old_files()

    def _generate_filename(
        self,
    ) -> str:
        captured_at = self._clock()

        if captured_at.tzinfo is None:
            captured_at = captured_at.replace(
                tzinfo=UTC,
            )

        timestamp = captured_at.astimezone(
            UTC,
        ).strftime(
            "%Y%m%d_%H%M%S_%f",
        )

        unique_token = self._token_factory()

        if not unique_token:
            raise ValueError("Runtime ROI filename token cannot be empty.")

        return f"{self._filename_prefix}_{timestamp}_{unique_token}.png"

    def _create_temporary_path(
        self,
        destination: Path,
    ) -> Path:
        with NamedTemporaryFile(
            mode="wb",
            prefix=f".{destination.stem}_",
            suffix=destination.suffix,
            dir=self._directory,
            delete=False,
        ) as temporary_file:
            return Path(
                temporary_file.name,
            )

    def _prune_old_files(
        self,
    ) -> None:
        expected_prefix = f"{self._filename_prefix}_"

        captured_files = [
            path
            for path in self._directory.iterdir()
            if (
                path.is_file()
                and path.name.startswith(
                    expected_prefix,
                )
                and path.suffix.lower() == ".png"
            )
        ]

        captured_files.sort(
            key=lambda path: (
                path == self._latest_path,
                path.name,
            ),
            reverse=True,
        )

        stale_files = captured_files[self._max_files :]

        for stale_path in stale_files:
            stale_path.unlink(
                missing_ok=True,
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
