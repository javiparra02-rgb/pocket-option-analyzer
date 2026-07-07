from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from pocket_option_analyzer.presentation.gui import MainWindow
from pocket_option_analyzer.presentation.signals import (
    SignalRecordViewModel,
)


def _application() -> QApplication:

    app = QApplication.instance()

    if app is None:
        app = QApplication(
            sys.argv,
        )

    return app


def test_main_window_has_initial_state() -> None:

    _application()

    window = MainWindow()

    assert window.windowTitle() == "Pocket Option Analyzer"
    assert window.status_text == "Estado: detenido"
    assert window.direction_text == "Señal: SIN SEÑAL"
    assert window.strength_text == "Fuerza: NINGUNA"
    assert window.reason_text == "Motivo: -"
    assert window.source_text == "Origen: -"
    assert window.created_at_text == "Fecha: -"


def test_main_window_updates_running_state() -> None:

    _application()

    window = MainWindow()

    window.set_running_state(
        is_running=True,
    )

    assert window.status_text == "Estado: ejecutando"

    window.set_running_state(
        is_running=False,
    )

    assert window.status_text == "Estado: detenido"


def test_main_window_updates_signal_view_model() -> None:

    _application()

    window = MainWindow()

    view_model = SignalRecordViewModel(
        direction_label="CALL",
        strength_label="ALTA",
        reason="Strategy conditions confirmed.",
        source="test_source",
        created_at_label="2026-01-01 10:30:45",
        is_actionable=True,
        css_class="signal-call",
    )

    window.update_signal(
        view_model=view_model,
    )

    assert window.direction_text == "Señal: CALL"
    assert window.strength_text == "Fuerza: ALTA"
    assert window.reason_text == "Motivo: Strategy conditions confirmed."
    assert window.source_text == "Origen: test_source"
    assert window.created_at_text == "Fecha: 2026-01-01 10:30:45"