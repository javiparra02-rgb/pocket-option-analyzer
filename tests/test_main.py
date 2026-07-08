from PySide6.QtWidgets import QApplication

from pocket_option_analyzer.main import (
    NoopRuntimeService,
    build_gui_application,
    ensure_qapplication,
)


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