from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from pocket_option_analyzer.presentation.gui import GuiApplication


class FakeWindow:

    def __init__(self) -> None:
        self.show_calls = 0

    def show(self) -> None:
        self.show_calls += 1


class FakeController:

    def __init__(self) -> None:
        self.window = FakeWindow()


def _application() -> QApplication:

    app = QApplication.instance()

    if app is None:
        app = QApplication(
            sys.argv,
        )

    return app


def test_gui_application_shows_controller_window(monkeypatch) -> None:

    app = _application()
    controller = FakeController()

    monkeypatch.setattr(
        app,
        "exec",
        lambda: 0,
    )

    gui_application = GuiApplication(
        controller=controller,
        argv=[
            "test",
        ],
    )

    result = gui_application.run()

    assert result == 0
    assert controller.window.show_calls == 1