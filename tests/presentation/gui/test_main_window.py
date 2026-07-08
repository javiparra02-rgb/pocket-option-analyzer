from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QPushButton

from pocket_option_analyzer.presentation.gui import MainWindow
from pocket_option_analyzer.presentation.signals import (
    SignalRecordViewModel,
)


class CallbackSpy:

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self) -> None:
        self.calls += 1


def _application() -> QApplication:

    app = QApplication.instance()

    if app is None:
        app = QApplication(
            sys.argv,
        )

    return app


def _button(
    window: MainWindow,
    object_name: str,
) -> QPushButton:

    button = window.findChild(
        QPushButton,
        object_name,
    )

    assert button is not None

    return button


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
    assert window.error_text == "Error: -"
    assert (
        window.capture_note_text
        == "Nota: no cubras el gráfico de Pocket Option con esta ventana. "
        "El análisis usa los píxeles visibles en pantalla."
    )


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


def test_main_window_calls_start_callback_when_start_button_is_clicked() -> None:

    _application()

    start_callback = CallbackSpy()

    window = MainWindow(
        on_start_requested=start_callback,
    )

    _button(
        window=window,
        object_name="start_button",
    ).click()

    assert start_callback.calls == 1


def test_main_window_calls_stop_callback_when_stop_button_is_clicked() -> None:

    _application()

    stop_callback = CallbackSpy()

    window = MainWindow(
        on_stop_requested=stop_callback,
    )

    window.set_running_state(
        is_running=True,
    )

    _button(
        window=window,
        object_name="stop_button",
    ).click()

    assert stop_callback.calls == 1


def test_main_window_calls_run_once_callback_when_run_once_button_is_clicked() -> None:

    _application()

    run_once_callback = CallbackSpy()

    window = MainWindow(
        on_run_once_requested=run_once_callback,
    )

    _button(
        window=window,
        object_name="run_once_button",
    ).click()

    assert run_once_callback.calls == 1


def test_main_window_displays_error_message() -> None:

    _application()

    window = MainWindow()

    window.set_error_message(
        "capture failed",
    )

    assert window.error_text == "Error: capture failed"

    window.set_error_message(
        None,
    )

    assert window.error_text == "Error: -"


def test_main_window_accepts_long_reason_without_losing_text() -> None:

    _application()

    window = MainWindow()

    long_reason = (
        "OTC Precision 10S conditions were not fully confirmed. "
        "CALL failed: EMA alignment is not bullish, "
        "EMA separation is insufficient, RSI is not in CALL range. "
        "PUT failed: trend is not bearish, EMA separation is insufficient, "
        "stochastic did not cross down."
    )

    view_model = SignalRecordViewModel(
        direction_label="SIN SEÑAL",
        strength_label="NINGUNA",
        reason=long_reason,
        source="captured_frame_visual_analysis",
        created_at_label="2026-07-08 14:19:29",
        is_actionable=False,
        css_class="signal-neutral",
    )

    window.update_signal(
        view_model=view_model,
    )

    assert window.reason_text == f"Motivo: {long_reason}"


def test_main_window_applies_call_style() -> None:

    _application()

    window = MainWindow()

    view_model = SignalRecordViewModel(
        direction_label="CALL",
        strength_label="ALTA",
        reason="CALL setup confirmed.",
        source="test_source",
        created_at_label="2026-01-01 10:30:45",
        is_actionable=True,
        css_class="signal-call",
    )

    window.update_signal(
        view_model=view_model,
    )

    assert "#0f9d58" in window.direction_style
    assert "#0f9d58" in window.strength_style
    assert "#0f9d58" in window.reason_style


def test_main_window_applies_put_style() -> None:

    _application()

    window = MainWindow()

    view_model = SignalRecordViewModel(
        direction_label="PUT",
        strength_label="ALTA",
        reason="PUT setup confirmed.",
        source="test_source",
        created_at_label="2026-01-01 10:30:45",
        is_actionable=True,
        css_class="signal-put",
    )

    window.update_signal(
        view_model=view_model,
    )

    assert "#d93025" in window.direction_style
    assert "#d93025" in window.strength_style
    assert "#d93025" in window.reason_style


def test_main_window_applies_neutral_style() -> None:

    _application()

    window = MainWindow()

    view_model = SignalRecordViewModel(
        direction_label="SIN SEÑAL",
        strength_label="NINGUNA",
        reason="No setup confirmed.",
        source="test_source",
        created_at_label="2026-01-01 10:30:45",
        is_actionable=False,
        css_class="signal-neutral",
    )

    window.update_signal(
        view_model=view_model,
    )

    assert "#5f6368" in window.direction_style
    assert "#5f6368" in window.strength_style
    assert "#9aa0a6" in window.reason_style


def test_main_window_initial_button_state() -> None:

    _application()

    window = MainWindow()

    assert window.start_button_enabled is True
    assert window.stop_button_enabled is False
    assert window.run_once_button_enabled is True


def test_main_window_disables_start_and_run_once_when_running() -> None:

    _application()

    window = MainWindow()

    window.set_running_state(
        is_running=True,
    )

    assert window.start_button_enabled is False
    assert window.stop_button_enabled is True
    assert window.run_once_button_enabled is False


def test_main_window_enables_start_and_run_once_when_stopped() -> None:

    _application()

    window = MainWindow()

    window.set_running_state(
        is_running=True,
    )
    window.set_running_state(
        is_running=False,
    )

    assert window.start_button_enabled is True
    assert window.stop_button_enabled is False
    assert window.run_once_button_enabled is True


def test_main_window_keeps_long_reason_scrolled_to_top() -> None:

    _application()

    window = MainWindow()

    long_reason = " ".join(
        f"condition-{index}"
        for index in range(100)
    )

    view_model = SignalRecordViewModel(
        direction_label="SIN SEÑAL",
        strength_label="NINGUNA",
        reason=long_reason,
        source="captured_frame_visual_analysis",
        created_at_label="2026-07-08 14:43:47",
        is_actionable=False,
        css_class="signal-neutral",
    )

    window.update_signal(
        view_model=view_model,
    )

    assert window.reason_text.startswith(
        "Motivo: condition-0"
    )
    assert window.reason_scroll_position == 0


def test_main_window_reason_panel_has_more_vertical_space() -> None:

    _application()

    window = MainWindow()

    assert window.reason_minimum_height >= 180
    assert window.minimumWidth() >= 520
    assert window.minimumHeight() >= 520


def test_main_window_displays_capture_note() -> None:

    _application()

    window = MainWindow()

    assert "no cubras el gráfico" in window.capture_note_text
    assert "píxeles visibles" in window.capture_note_text


def test_main_window_can_hide_and_show_for_capture() -> None:

    _application()

    window = MainWindow()
    window.show()

    assert window.isVisible() is True

    window.hide_for_capture()

    assert window.isVisible() is False

    window.show_after_capture()

    assert window.isVisible() is True