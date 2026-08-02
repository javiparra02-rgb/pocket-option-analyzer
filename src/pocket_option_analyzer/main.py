from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

from PySide6.QtWidgets import QApplication

from pocket_option_analyzer.application.session_results import (
    ManualSignalResultSessionService,
)
from pocket_option_analyzer.infrastructure.audio import (
    QtTextToSpeechAdapter,
)
from pocket_option_analyzer.infrastructure.bootstrap import (
    PocketOptionRuntimeFactory,
)
from pocket_option_analyzer.infrastructure.config import (
    get_settings,
)
from pocket_option_analyzer.infrastructure.logging import (
    LoggingManager,
)
from pocket_option_analyzer.infrastructure.persistence import (
    JsonlManualSignalResultWriter,
)
from pocket_option_analyzer.infrastructure.windows import (
    WindowsRecordingSafetyGuard,
    WindowsWindowCaptureExcluder,
)
from pocket_option_analyzer.presentation.gui import (
    GuiApplication,
    MainWindowController,
)
from pocket_option_analyzer.presentation.signals import (
    VoiceSignalNotifier,
)


class NoopRuntimeService:
    """
    Runtime temporal para pruebas.

    La aplicación real usa PocketOptionRuntimeFactory.
    """

    @property
    def is_running(self) -> bool:
        return False

    def run_once(self):
        return None

    def start(
        self,
        max_iterations: int | None = None,
    ) -> None:
        return None

    def stop(self) -> None:
        return None


def ensure_qapplication(
    argv: Sequence[str] | None = None,
) -> QApplication:
    """
    Garantiza que QApplication exista antes de crear cualquier QWidget.
    """

    app = QApplication.instance()

    if app is not None:
        return app

    return QApplication(list(argv if argv is not None else sys.argv))


DEFAULT_MANUAL_RESULT_FILE_PATH = Path("logs") / "manual_signal_results.jsonl"


def build_gui_application(
    argv: Sequence[str] | None = None,
    runtime_service=None,
    voice_notifier: VoiceSignalNotifier | None = None,
    manual_result_session: ManualSignalResultSessionService | None = None,
    window_capture_excluder: WindowsWindowCaptureExcluder | None = None,
    recording_safety_guard: WindowsRecordingSafetyGuard | None = None,
) -> GuiApplication:
    """
    Construye la aplicación gráfica.

    Si no se entrega runtime_service, construye el runtime real para
    capturar y analizar Pocket Option.
    """

    ensure_qapplication(
        argv=argv,
    )

    resolved_runtime_service = (
        runtime_service
        if runtime_service is not None
        else PocketOptionRuntimeFactory.create_runtime_service()
    )

    resolved_voice_notifier = voice_notifier

    if resolved_voice_notifier is None and runtime_service is None:
        resolved_voice_notifier = VoiceSignalNotifier(
            speech_engine=QtTextToSpeechAdapter(),
        )

    resolved_manual_result_session = manual_result_session
    resolved_window_capture_excluder = window_capture_excluder
    resolved_recording_safety_guard = recording_safety_guard

    if resolved_recording_safety_guard is None and runtime_service is None:
        resolved_recording_safety_guard = WindowsRecordingSafetyGuard(
            target_title_fragment="Pocket Option",
            safety_margin_px=8,
        )

    if resolved_window_capture_excluder is None and runtime_service is None:
        resolved_window_capture_excluder = WindowsWindowCaptureExcluder()

    if resolved_manual_result_session is None and runtime_service is None:
        resolved_manual_result_session = ManualSignalResultSessionService(
            writer=JsonlManualSignalResultWriter(
                output_path=DEFAULT_MANUAL_RESULT_FILE_PATH,
            ),
        )

    controller = MainWindowController(
        runtime_service=resolved_runtime_service,
        voice_notifier=resolved_voice_notifier,
        manual_result_session=resolved_manual_result_session,
        window_capture_excluder=resolved_window_capture_excluder,
        recording_safety_guard=resolved_recording_safety_guard,
    )

    return GuiApplication(
        controller=controller,
        argv=argv,
    )


def main(
    argv: Sequence[str] | None = None,
    logging_manager: LoggingManager | None = None,
) -> int:
    """
    Punto de entrada principal de la aplicación.

    Configura el logger técnico antes de construir la GUI y garantiza
    que los mensajes encolados se escriban antes de finalizar.
    """

    resolved_logging_manager = (
        logging_manager
        if logging_manager is not None
        else LoggingManager(
            settings=get_settings(),
        )
    )

    resolved_logging_manager.configure()

    application_logger = resolved_logging_manager.logger

    application_logger.info("Iniciando Pocket Option Analyzer.")

    try:
        application = build_gui_application(
            argv=argv,
        )

        exit_code = application.run()

        application_logger.info(
            f"Pocket Option Analyzer finalizado con código {exit_code}."
        )

        return exit_code

    except Exception:
        application_logger.exception(
            "Error no controlado durante la ejecución de Pocket Option Analyzer."
        )
        raise

    finally:
        resolved_logging_manager.shutdown()
