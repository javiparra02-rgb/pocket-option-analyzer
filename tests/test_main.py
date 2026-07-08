from pocket_option_analyzer.main import (
    NoopRuntimeService,
    build_gui_application,
)


def test_noop_runtime_service_is_not_running() -> None:

    runtime = NoopRuntimeService()

    assert runtime.is_running is False
    assert runtime.run_once() is None
    assert runtime.start() is None
    assert runtime.stop() is None


def test_build_gui_application_returns_application() -> None:

    application = build_gui_application(
        argv=[
            "test",
        ],
    )

    assert application is not None