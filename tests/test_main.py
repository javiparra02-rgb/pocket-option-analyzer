import pytest
from PySide6.QtWidgets import QApplication

import pocket_option_analyzer.main as main_module
from pocket_option_analyzer.main import (
    NoopRuntimeService,
    build_gui_application,
    ensure_qapplication,
)


class FakeApplicationLogger:

    def __init__(
        self,
    ) -> None:
        self.info_messages: list[str] = []
        self.exception_messages: list[str] = []

    def info(
        self,
        message: str,
    ) -> None:
        self.info_messages.append(
            message,
        )

    def exception(
        self,
        message: str,
    ) -> None:
        self.exception_messages.append(
            message,
        )


class FakeLoggingManager:

    def __init__(
        self,
    ) -> None:
        self.logger = FakeApplicationLogger()
        self.configure_calls = 0
        self.shutdown_calls = 0

    def configure(
        self,
    ) -> None:
        self.configure_calls += 1

    def shutdown(
        self,
    ) -> None:
        self.shutdown_calls += 1


class FakeGuiApplication:

    def __init__(
        self,
        exit_code: int = 0,
        error: Exception | None = None,
    ) -> None:
        self.exit_code = exit_code
        self.error = error
        self.run_calls = 0

    def run(
        self,
    ) -> int:
        self.run_calls += 1

        if self.error is not None:
            raise self.error

        return self.exit_code


def test_noop_runtime_service_is_not_running() -> None:

    runtime = NoopRuntimeService()

    assert runtime.is_running is False
    assert runtime.run_once() is None
    assert runtime.start() is None
    assert runtime.stop() is None


def test_ensure_qapplication_returns_qapplication_instance() -> None:

    app = ensure_qapplication(
        argv=[
            "test",
        ],
    )

    assert app is QApplication.instance()


def test_build_gui_application_returns_application_with_injected_runtime() -> None:

    application = build_gui_application(
        argv=[
            "test",
        ],
        runtime_service=NoopRuntimeService(),
    )

    assert application is not None
    assert QApplication.instance() is not None


def test_main_configures_and_closes_logging_manager(
    monkeypatch,
) -> None:

    gui_application = FakeGuiApplication(
        exit_code=7,
    )

    logging_manager = FakeLoggingManager()

    monkeypatch.setattr(
        main_module,
        "build_gui_application",
        lambda argv=None: gui_application,
    )

    result = main_module.main(
        argv=[
            "test",
        ],
        logging_manager=logging_manager,
    )

    assert result == 7
    assert gui_application.run_calls == 1
    assert logging_manager.configure_calls == 1
    assert logging_manager.shutdown_calls == 1

    assert logging_manager.logger.info_messages == [
        "Iniciando Pocket Option Analyzer.",
        (
            "Pocket Option Analyzer finalizado "
            "con código 7."
        ),
    ]


def test_main_logs_unhandled_error_and_flushes_logger(
    monkeypatch,
) -> None:

    gui_application = FakeGuiApplication(
        error=RuntimeError(
            "GUI failure.",
        ),
    )

    logging_manager = FakeLoggingManager()

    monkeypatch.setattr(
        main_module,
        "build_gui_application",
        lambda argv=None: gui_application,
    )

    with pytest.raises(
        RuntimeError,
        match="GUI failure",
    ):
        main_module.main(
            argv=[
                "test",
            ],
            logging_manager=logging_manager,
        )

    assert logging_manager.configure_calls == 1
    assert logging_manager.shutdown_calls == 1

    assert logging_manager.logger.exception_messages == [
        (
            "Error no controlado durante "
            "la ejecución de Pocket Option Analyzer."
        ),
    ]