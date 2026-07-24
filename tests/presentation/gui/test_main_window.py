from __future__ import annotations

import sys

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QPushButton

from pocket_option_analyzer.presentation.gui import MainWindow
from pocket_option_analyzer.presentation.signals import (
    SessionResult,
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


def _confirmed_signal(
    index: int,
    direction: str = "CALL",
) -> SignalRecordViewModel:
    return SignalRecordViewModel(
        direction_label=direction,
        strength_label="ALTA",
        reason=f"{direction} setup confirmed.",
        source="test_source",
        created_at_label=f"2026-01-01 11:00:{index:02d}",
        is_actionable=True,
        css_class=(
            "signal-call"
            if direction == "CALL"
            else "signal-put"
        ),
        operational_summary_label=(
            f"Resumen operativo: ENTRADA {direction} confirmada — "
            "revisar gestión de riesgo antes de operar manualmente."
        ),
    )


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
    assert window.visual_diagnostics_text == "Diagnóstico visual: -"
    assert window.indicator_diagnostics_text == "Diagnóstico de indicadores: -"
    assert window.error_text == "Error: -"
    assert window.operational_summary_text == "Resumen operativo: ESPERAR"
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
    assert window.minimumWidth() >= 460
    assert window.minimumHeight() >= 360


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


def test_main_window_initial_signal_history_is_empty() -> None:

    _application()

    window = MainWindow()

    assert window.signal_history_count == 0
    assert window.latest_signal_history_text is None


def test_main_window_appends_signal_to_history() -> None:

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

    assert window.signal_history_count == 1
    assert (
        window.latest_signal_history_text
        == "2026-01-01 10:30:45 | CALL | ALTA"
    )


def test_main_window_keeps_latest_signal_at_top_of_history() -> None:

    _application()

    window = MainWindow()

    first = SignalRecordViewModel(
        direction_label="CALL",
        strength_label="ALTA",
        reason="CALL setup confirmed.",
        source="test_source",
        created_at_label="2026-01-01 10:30:45",
        is_actionable=True,
        css_class="signal-call",
    )

    second = SignalRecordViewModel(
        direction_label="PUT",
        strength_label="ALTA",
        reason="PUT setup confirmed.",
        source="test_source",
        created_at_label="2026-01-01 10:31:45",
        is_actionable=True,
        css_class="signal-put",
    )

    window.update_signal(
        view_model=first,
    )
    window.update_signal(
        view_model=second,
    )

    assert window.signal_history_count == 2
    assert (
        window.latest_signal_history_text
        == "2026-01-01 10:31:45 | PUT | ALTA"
    )


def test_main_window_limits_signal_history_size() -> None:

    _application()

    window = MainWindow()

    for index in range(55):
        view_model = SignalRecordViewModel(
            direction_label="SIN SEÑAL",
            strength_label="NINGUNA",
            reason="No setup confirmed.",
            source="test_source",
            created_at_label=f"2026-01-01 10:30:{index:02d}",
            is_actionable=False,
            css_class="signal-neutral",
        )

        window.update_signal(
            view_model=view_model,
        )

    assert window.signal_history_count == window.max_signal_history_items
    assert (
        window.latest_signal_history_text
        == "2026-01-01 10:30:54 | SIN SEÑAL | NINGUNA"
    )
    assert (
        window.signal_history_texts[-1]
        == "2026-01-01 10:30:05 | SIN SEÑAL | NINGUNA"
    )


def test_main_window_clears_signal_history() -> None:

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

    assert window.signal_history_count == 1

    window.clear_signal_history()

    assert window.signal_history_count == 0
    assert window.latest_signal_history_text is None


def test_main_window_clear_history_button_clears_history() -> None:

    _application()

    window = MainWindow()

    view_model = SignalRecordViewModel(
        direction_label="PUT",
        strength_label="ALTA",
        reason="PUT setup confirmed.",
        source="test_source",
        created_at_label="2026-01-01 10:31:45",
        is_actionable=True,
        css_class="signal-put",
    )

    window.update_signal(
        view_model=view_model,
    )

    assert window.signal_history_count == 1

    _button(
        window=window,
        object_name="clear_history_button",
    ).click()

    assert window.signal_history_count == 0
    assert window.latest_signal_history_text is None


def test_main_window_uses_scrollable_content() -> None:

    _application()

    window = MainWindow()

    assert window.has_scrollable_content is True


def test_main_window_updates_visual_diagnostics() -> None:

    _application()

    window = MainWindow()

    visual_text = (
        "Diagnóstico visual:\n"
        "  Tendencia: BEARISH\n"
        "  Velas detectadas: 24\n"
        "  Últimas: BEARISH, BULLISH, BEARISH\n"
        "  Cerradas: BEARISH, BEARISH, BULLISH\n"
        "  Direccionales: BEARISH, BEARISH, BULLISH\n"
        "  Contexto: BEARISH_PULLBACK\n"
        "  Vigilancia: ESPERAR\n"
        "  Estado: ESPERANDO_CONFIRMACION"
    )

    view_model = SignalRecordViewModel(
        direction_label="SIN SEÑAL",
        strength_label="NINGUNA",
        reason="No setup confirmed.",
        source="test_source",
        created_at_label="2026-01-01 10:30:45",
        is_actionable=False,
        css_class="signal-neutral",
        visual_diagnostics_label=visual_text,
        indicator_diagnostics_label="Diagnóstico de indicadores: -",
    )

    window.update_signal(
        view_model=view_model,
    )

    assert window.visual_diagnostics_text == visual_text


def test_main_window_updates_indicator_diagnostics() -> None:

    _application()

    window = MainWindow()

    indicator_text = (
        "Diagnóstico de indicadores:\n"
        "  EMA: bajista | rápida=10.00 | lenta=12.00 | "
        "separación=3/3 suficiente\n"
        "  RSI: 42.00 | CALL fuera de rango | PUT en rango\n"
        "  Stochastic: cruce bajista | K=76.00 | D=78.00 | "
        "prevK=82.00 | prevD=80.00\n"
        "  Estado: esperando confirmación de estrategia"
    )

    view_model = SignalRecordViewModel(
        direction_label="SIN SEÑAL",
        strength_label="NINGUNA",
        reason="No setup confirmed.",
        source="test_source",
        created_at_label="2026-01-01 10:30:45",
        is_actionable=False,
        css_class="signal-neutral",
        visual_diagnostics_label="Diagnóstico visual: Tendencia: BEARISH",
        indicator_diagnostics_label=indicator_text,
    )

    window.update_signal(
        view_model=view_model,
    )

    assert window.indicator_diagnostics_text == indicator_text


def test_main_window_updates_operational_summary() -> None:

    _application()

    window = MainWindow()

    view_model = SignalRecordViewModel(
        direction_label="SIN SEÑAL",
        strength_label="NINGUNA",
        reason="Technical detail hidden from main view.",
        source="test_source",
        created_at_label="2026-01-01 10:30:45",
        is_actionable=False,
        css_class="signal-neutral",
        visual_diagnostics_label="Diagnóstico visual: Tendencia: BEARISH",
        indicator_diagnostics_label="Diagnóstico de indicadores: -",
        operational_summary_label=(
            "Resumen operativo: VIGILAR PUT — falta confirmación "
            "completa de la estrategia."
        ),
    )

    window.update_signal(
        view_model=view_model,
    )

    assert (
        window.operational_summary_text
        == "Resumen operativo: VIGILAR PUT — falta confirmación "
        "completa de la estrategia."
    )


def test_main_window_has_compact_signal_history() -> None:

    _application()

    window = MainWindow()

    assert window.signal_history_maximum_height == 90


def test_main_window_starts_with_full_view_mode() -> None:

    _application()

    window = MainWindow()

    assert window.is_compact_mode_enabled is False
    assert window.compact_mode_button_text == "Modo compacto"
    assert window.visual_diagnostics_visible is True
    assert window.indicator_diagnostics_visible is True
    assert window.signal_history_visible is True


def test_main_window_toggles_compact_mode() -> None:

    _application()

    window = MainWindow()

    window._compact_mode_button.click()

    assert window.is_compact_mode_enabled is True
    assert window.compact_mode_button_text == "Vista completa"
    assert window.visual_diagnostics_visible is False
    assert window.indicator_diagnostics_visible is False
    assert window.signal_history_visible is False

    window._compact_mode_button.click()

    assert window.is_compact_mode_enabled is False
    assert window.compact_mode_button_text == "Modo compacto"
    assert window.visual_diagnostics_visible is True
    assert window.indicator_diagnostics_visible is True
    assert window.signal_history_visible is True


def test_main_window_uses_full_window_geometry_by_default() -> None:

    _application()

    window = MainWindow()

    assert window.window_size == (
        MainWindow.FULL_WINDOW_WIDTH,
        MainWindow.FULL_WINDOW_HEIGHT,
    )
    assert window.minimum_window_size == (
        MainWindow.FULL_MIN_WIDTH,
        MainWindow.FULL_MIN_HEIGHT,
    )
    assert window.layout_spacing == MainWindow.FULL_LAYOUT_SPACING


def test_main_window_resizes_when_compact_mode_is_enabled() -> None:

    _application()

    window = MainWindow()

    window._compact_mode_button.click()

    assert window.window_size == (
        MainWindow.COMPACT_WINDOW_WIDTH,
        MainWindow.COMPACT_WINDOW_HEIGHT,
    )
    assert window.minimum_window_size == (
        MainWindow.COMPACT_MIN_WIDTH,
        MainWindow.COMPACT_MIN_HEIGHT,
    )
    assert window.layout_spacing == MainWindow.COMPACT_LAYOUT_SPACING


def test_main_window_restores_full_geometry_when_compact_mode_is_disabled() -> None:

    _application()

    window = MainWindow()

    window._compact_mode_button.click()
    window._compact_mode_button.click()

    assert window.window_size == (
        MainWindow.FULL_WINDOW_WIDTH,
        MainWindow.FULL_WINDOW_HEIGHT,
    )
    assert window.minimum_window_size == (
        MainWindow.FULL_MIN_WIDTH,
        MainWindow.FULL_MIN_HEIGHT,
    )
    assert window.layout_spacing == MainWindow.FULL_LAYOUT_SPACING


def _temporary_settings(
    tmp_path,
) -> QSettings:
    return QSettings(
        str(
            tmp_path / "window_settings.ini",
        ),
        QSettings.Format.IniFormat,
    )


def test_main_window_does_not_restore_preferences_by_default(
    tmp_path,
) -> None:

    _application()

    settings = _temporary_settings(
        tmp_path,
    )

    settings.beginGroup(
        MainWindow.SETTINGS_GROUP,
    )
    settings.setValue(
        MainWindow.SETTING_COMPACT_MODE,
        True,
    )
    settings.setValue(
        MainWindow.SETTING_WIDTH,
        430,
    )
    settings.setValue(
        MainWindow.SETTING_HEIGHT,
        280,
    )
    settings.endGroup()
    settings.sync()

    window = MainWindow(
        settings=settings,
    )

    assert window.is_compact_mode_enabled is False
    assert window.window_size == (
        MainWindow.FULL_WINDOW_WIDTH,
        MainWindow.FULL_WINDOW_HEIGHT,
    )


def test_main_window_restores_saved_compact_preferences(
    tmp_path,
) -> None:

    _application()

    settings = _temporary_settings(
        tmp_path,
    )

    settings.beginGroup(
        MainWindow.SETTINGS_GROUP,
    )
    settings.setValue(
        MainWindow.SETTING_COMPACT_MODE,
        True,
    )
    settings.setValue(
        MainWindow.SETTING_X,
        100,
    )
    settings.setValue(
        MainWindow.SETTING_Y,
        120,
    )
    settings.setValue(
        MainWindow.SETTING_WIDTH,
        430,
    )
    settings.setValue(
        MainWindow.SETTING_HEIGHT,
        280,
    )
    settings.endGroup()
    settings.sync()

    window = MainWindow(
        settings=settings,
        restore_window_preferences=True,
    )

    assert window.is_compact_mode_enabled is True
    assert window.compact_mode_button_text == "Vista completa"
    assert window.window_size == (
        430,
        280,
    )


def test_main_window_saves_window_preferences_when_enabled(
    tmp_path,
) -> None:

    _application()

    settings = _temporary_settings(
        tmp_path,
    )

    window = MainWindow(
        settings=settings,
        restore_window_preferences=True,
    )

    window._compact_mode_button.click()

    settings.beginGroup(
        MainWindow.SETTINGS_GROUP,
    )

    assert settings.value(
        MainWindow.SETTING_COMPACT_MODE,
        type=bool,
    ) is True
    assert settings.value(
        MainWindow.SETTING_WIDTH,
        type=int,
    ) == MainWindow.COMPACT_WINDOW_WIDTH
    assert settings.value(
        MainWindow.SETTING_HEIGHT,
        type=int,
    ) == MainWindow.COMPACT_WINDOW_HEIGHT

    settings.endGroup()


def test_main_window_has_reset_view_button() -> None:

    _application()

    window = MainWindow()

    assert window.reset_view_button_text == "Restablecer vista"


def test_main_window_reset_view_restores_full_mode() -> None:

    _application()

    window = MainWindow()

    window._compact_mode_button.click()

    assert window.is_compact_mode_enabled is True

    _button(
        window=window,
        object_name="reset_view_button",
    ).click()

    assert window.is_compact_mode_enabled is False
    assert window.compact_mode_button_text == "Modo compacto"
    assert window.window_size == (
        MainWindow.FULL_WINDOW_WIDTH,
        MainWindow.FULL_WINDOW_HEIGHT,
    )
    assert window.minimum_window_size == (
        MainWindow.FULL_MIN_WIDTH,
        MainWindow.FULL_MIN_HEIGHT,
    )
    assert window.visual_diagnostics_visible is True
    assert window.indicator_diagnostics_visible is True
    assert window.signal_history_visible is True


def test_main_window_reset_view_saves_clean_preferences(
    tmp_path,
) -> None:

    _application()

    settings = _temporary_settings(
        tmp_path,
    )

    window = MainWindow(
        settings=settings,
        restore_window_preferences=True,
    )

    window._compact_mode_button.click()

    assert window.is_compact_mode_enabled is True

    _button(
        window=window,
        object_name="reset_view_button",
    ).click()

    settings.beginGroup(
        MainWindow.SETTINGS_GROUP,
    )

    assert settings.value(
        MainWindow.SETTING_COMPACT_MODE,
        type=bool,
    ) is False
    assert settings.value(
        MainWindow.SETTING_WIDTH,
        type=int,
    ) == MainWindow.FULL_WINDOW_WIDTH
    assert settings.value(
        MainWindow.SETTING_HEIGHT,
        type=int,
    ) == MainWindow.FULL_WINDOW_HEIGHT

    settings.endGroup()


def test_main_window_compact_mode_prioritizes_live_summary() -> None:

    _application()

    window = MainWindow()

    window._compact_mode_button.click()

    assert window.is_compact_mode_enabled is True

    assert window.signal_label_visible is True
    assert window.strength_label_visible is True
    assert window.operational_summary_visible is True

    assert window.visual_diagnostics_visible is False
    assert window.indicator_diagnostics_visible is False
    assert window.signal_history_visible is False


def test_main_window_styles_operational_summary_for_call_watch() -> None:

    _application()

    window = MainWindow()

    view_model = SignalRecordViewModel(
        direction_label="SIN SEÑAL",
        strength_label="NINGUNA",
        reason="Waiting for CALL confirmation.",
        source="test_source",
        created_at_label="2026-01-01 10:30:45",
        is_actionable=False,
        css_class="signal-neutral",
        operational_summary_label=(
            "Resumen operativo: VIGILAR CALL — falta confirmación "
            "completa de la estrategia."
        ),
    )

    window.update_signal(
        view_model=view_model,
    )

    assert "#0f9d58" in window.operational_summary_style
    assert "#eefaf3" in window.operational_summary_style


def test_main_window_styles_operational_summary_for_put_watch() -> None:

    _application()

    window = MainWindow()

    view_model = SignalRecordViewModel(
        direction_label="SIN SEÑAL",
        strength_label="NINGUNA",
        reason="Waiting for PUT confirmation.",
        source="test_source",
        created_at_label="2026-01-01 10:30:45",
        is_actionable=False,
        css_class="signal-neutral",
        operational_summary_label=(
            "Resumen operativo: VIGILAR PUT — falta confirmación "
            "completa de la estrategia."
        ),
    )

    window.update_signal(
        view_model=view_model,
    )

    assert "#d93025" in window.operational_summary_style
    assert "#fff0f0" in window.operational_summary_style


def test_main_window_styles_operational_summary_as_neutral_when_waiting() -> None:

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
        operational_summary_label="Resumen operativo: ESPERAR",
    )

    window.update_signal(
        view_model=view_model,
    )

    assert "#5f6368" in window.operational_summary_style
    assert "#f8f9fa" in window.operational_summary_style


def test_main_window_styles_operational_summary_for_confirmed_call_entry() -> None:

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
        operational_summary_label=(
            "Resumen operativo: ENTRADA CALL confirmada — revisar gestión "
            "de riesgo antes de operar manualmente."
        ),
    )

    window.update_signal(
        view_model=view_model,
    )

    assert "#0f9d58" in window.operational_summary_style
    assert "#eefaf3" in window.operational_summary_style


def test_main_window_styles_operational_summary_for_confirmed_put_entry() -> None:

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
        operational_summary_label=(
            "Resumen operativo: ENTRADA PUT confirmada — revisar gestión "
            "de riesgo antes de operar manualmente."
        ),
    )

    window.update_signal(
        view_model=view_model,
    )

    assert "#d93025" in window.operational_summary_style
    assert "#fff0f0" in window.operational_summary_style


def test_main_window_hides_entry_alert_by_default() -> None:

    _application()

    window = MainWindow()

    assert window.entry_alert_visible is False
    assert window.entry_alert_text == ""


def test_main_window_shows_call_entry_alert_when_signal_is_actionable() -> None:

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
        operational_summary_label=(
            "Resumen operativo: ENTRADA CALL confirmada — revisar gestión "
            "de riesgo antes de operar manualmente."
        ),
    )

    window.update_signal(
        view_model=view_model,
    )

    assert window.entry_alert_visible is True
    assert window.entry_alert_text == "ENTRADA CALL CONFIRMADA"
    assert "#0f9d58" in window.entry_alert_style


def test_main_window_shows_put_entry_alert_when_signal_is_actionable() -> None:

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
        operational_summary_label=(
            "Resumen operativo: ENTRADA PUT confirmada — revisar gestión "
            "de riesgo antes de operar manualmente."
        ),
    )

    window.update_signal(
        view_model=view_model,
    )

    assert window.entry_alert_visible is True
    assert window.entry_alert_text == "ENTRADA PUT CONFIRMADA"
    assert "#d93025" in window.entry_alert_style


def test_main_window_hides_entry_alert_when_signal_is_not_actionable() -> None:

    _application()

    window = MainWindow()

    actionable_view_model = SignalRecordViewModel(
        direction_label="PUT",
        strength_label="ALTA",
        reason="PUT setup confirmed.",
        source="test_source",
        created_at_label="2026-01-01 10:30:45",
        is_actionable=True,
        css_class="signal-put",
        operational_summary_label=(
            "Resumen operativo: ENTRADA PUT confirmada — revisar gestión "
            "de riesgo antes de operar manualmente."
        ),
    )

    neutral_view_model = SignalRecordViewModel(
        direction_label="SIN SEÑAL",
        strength_label="NINGUNA",
        reason="No setup confirmed.",
        source="test_source",
        created_at_label="2026-01-01 10:31:45",
        is_actionable=False,
        css_class="signal-neutral",
        operational_summary_label="Resumen operativo: ESPERAR",
    )

    window.update_signal(
        view_model=actionable_view_model,
    )

    assert window.entry_alert_visible is True

    window.update_signal(
        view_model=neutral_view_model,
    )

    assert window.entry_alert_visible is False
    assert window.entry_alert_text == ""


def test_main_window_displays_initial_confirmation_checklist() -> None:

    _application()

    window = MainWindow()

    assert (
        window.confirmation_checklist_text
        == "Visual: ❌ | EMA: ❌ | RSI: ❌ | Stoch: ❌ | Entrada: ESPERAR"
    )
    assert window.confirmation_checklist_visible is True


def test_main_window_updates_confirmation_checklist_for_put_watch() -> None:

    _application()

    window = MainWindow()

    view_model = SignalRecordViewModel(
        direction_label="SIN SEÑAL",
        strength_label="NINGUNA",
        reason="Waiting for PUT confirmation.",
        source="test_source",
        created_at_label="2026-01-01 10:30:45",
        is_actionable=False,
        css_class="signal-neutral",
        visual_diagnostics_label=(
            "Diagnóstico visual:\n"
            "  Tendencia: BEARISH\n"
            "  Contexto: BEARISH_CONTINUATION\n"
            "  Vigilancia: VIGILAR_PUT\n"
            "  Estado: ESPERANDO_CONFIRMACION"
        ),
        indicator_diagnostics_label=(
            "Diagnóstico de indicadores:\n"
            "  EMA: bajista | rápida=89.09 | lenta=161.44 | "
            "separación=8/3 suficiente\n"
            "  RSI: 36.64 | CALL fuera de rango | PUT en rango\n"
            "  Stochastic: sin cruce | K=70.00 | D=60.00\n"
            "  Estado: esperando confirmación de estrategia"
        ),
        operational_summary_label=(
            "Resumen operativo: VIGILAR PUT — falta confirmación "
            "completa de la estrategia."
        ),
    )

    window.update_signal(
        view_model=view_model,
    )

    assert (
        window.confirmation_checklist_text
        == "Visual: ❌ | EMA: ✅ | RSI: ✅ | Stoch: ❌ | Entrada: ESPERAR"
    )


def test_main_window_updates_confirmation_checklist_for_confirmed_put() -> None:

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
        visual_diagnostics_label=(
            "Diagnóstico visual:\n"
            "  Tendencia: BEARISH\n"
            "  Contexto: BEARISH_CONTINUATION\n"
            "  Vigilancia: VIGILAR_PUT\n"
            "  Estado: SEÑAL_CONFIRMADA"
        ),
        indicator_diagnostics_label=(
            "Diagnóstico de indicadores:\n"
            "  EMA: bajista | rápida=89.09 | lenta=161.44 | "
            "separación=8/3 suficiente\n"
            "  RSI: 36.64 | CALL fuera de rango | PUT en rango\n"
            "  Stochastic: cruce bajista | K=70.00 | D=80.00\n"
            "  Estado: esperando confirmación de estrategia"
        ),
        operational_summary_label=(
            "Resumen operativo: ENTRADA PUT confirmada — revisar gestión "
            "de riesgo antes de operar manualmente."
        ),
    )

    window.update_signal(
        view_model=view_model,
    )

    assert (
        window.confirmation_checklist_text
        == "Visual: ✅ | EMA: ✅ | RSI: ✅ | Stoch: ✅ | Entrada: PUT"
    )
    assert "#d93025" in window.confirmation_checklist_style


def test_main_window_keeps_confirmation_checklist_visible_in_compact_mode() -> None:

    _application()

    window = MainWindow()

    window._compact_mode_button.click()

    assert window.is_compact_mode_enabled is True
    assert window.confirmation_checklist_visible is True


def test_main_window_marks_call_ema_as_missing_when_separation_is_insufficient() -> None:

    _application()

    window = MainWindow()

    view_model = SignalRecordViewModel(
        direction_label="SIN SEÑAL",
        strength_label="NINGUNA",
        reason="Waiting for CALL confirmation.",
        source="test_source",
        created_at_label="2026-01-01 10:30:45",
        is_actionable=False,
        css_class="signal-neutral",
        visual_diagnostics_label=(
            "Diagnóstico visual:\n"
            "  Tendencia: BULLISH\n"
            "  Contexto: BULLISH_CONTINUATION\n"
            "  Vigilancia: VIGILAR_CALL\n"
            "  Estado: ESPERANDO_CONFIRMACION"
        ),
        indicator_diagnostics_label=(
            "Diagnóstico de indicadores:\n"
            "  EMA: alcista | rápida=318.00 | lenta=227.10 | "
            "separación=1/3 insuficiente\n"
            "  RSI: 57.00 | CALL en rango | PUT fuera de rango\n"
            "  Stochastic: cruce alcista | K=70.00 | D=60.00\n"
            "  Estado: esperando confirmación de estrategia"
        ),
        operational_summary_label=(
            "Resumen operativo: VIGILAR CALL — falta confirmación "
            "completa de la estrategia."
        ),
    )

    window.update_signal(
        view_model=view_model,
    )

    assert (
        window.confirmation_checklist_text
        == "Visual: ❌ | EMA: ❌ | RSI: ✅ | Stoch: ✅ | Entrada: ESPERAR"
    )


def test_main_window_marks_put_ema_as_missing_when_separation_is_insufficient() -> None:

    _application()

    window = MainWindow()

    view_model = SignalRecordViewModel(
        direction_label="SIN SEÑAL",
        strength_label="NINGUNA",
        reason="Waiting for PUT confirmation.",
        source="test_source",
        created_at_label="2026-01-01 10:30:45",
        is_actionable=False,
        css_class="signal-neutral",
        visual_diagnostics_label=(
            "Diagnóstico visual:\n"
            "  Tendencia: BEARISH\n"
            "  Contexto: BEARISH_CONTINUATION\n"
            "  Vigilancia: VIGILAR_PUT\n"
            "  Estado: ESPERANDO_CONFIRMACION"
        ),
        indicator_diagnostics_label=(
            "Diagnóstico de indicadores:\n"
            "  EMA: bajista | rápida=309.10 | lenta=365.78 | "
            "separación=2/3 insuficiente\n"
            "  RSI: 69.11 | CALL fuera de rango | PUT fuera de rango\n"
            "  Stochastic: cruce bajista | K=33.33 | D=14.75\n"
            "  Estado: esperando confirmación de estrategia"
        ),
        operational_summary_label=(
            "Resumen operativo: VIGILAR PUT — falta confirmación "
            "completa de la estrategia."
        ),
    )

    window.update_signal(
        view_model=view_model,
    )

    assert (
        window.confirmation_checklist_text
        == "Visual: ❌ | EMA: ❌ | RSI: ❌ | Stoch: ✅ | Entrada: ESPERAR"
    )


def test_main_window_keeps_visual_missing_when_all_indicators_are_ready_but_signal_is_not_confirmed() -> None:

    _application()

    window = MainWindow()

    view_model = SignalRecordViewModel(
        direction_label="SIN SEÑAL",
        strength_label="NINGUNA",
        reason="Waiting for final visual confirmation.",
        source="test_source",
        created_at_label="2026-01-01 10:30:45",
        is_actionable=False,
        css_class="signal-neutral",
        visual_diagnostics_label=(
            "Diagnóstico visual:\n"
            "  Tendencia: BEARISH\n"
            "  Contexto: BEARISH_CONTINUATION\n"
            "  Vigilancia: VIGILAR_PUT\n"
            "  Estado: ESPERANDO_CONFIRMACION"
        ),
        indicator_diagnostics_label=(
            "Diagnóstico de indicadores:\n"
            "  EMA: bajista | rápida=108.14 | lenta=183.32 | "
            "separación=9/3 suficiente\n"
            "  RSI: 39.62 | CALL fuera de rango | PUT en rango\n"
            "  Stochastic: cruce bajista | K=12.60 | D=15.25 | "
            "prevK=16.58 | prevD=16.58\n"
            "  Estado: esperando confirmación de estrategia"
        ),
        operational_summary_label=(
            "Resumen operativo: VIGILAR PUT — falta confirmación "
            "completa de la estrategia."
        ),
    )

    window.update_signal(
        view_model=view_model,
    )

    assert (
        window.confirmation_checklist_text
        == "Visual: ❌ | EMA: ✅ | RSI: ✅ | Stoch: ✅ | Entrada: ESPERAR"
    )


def test_main_window_displays_initial_session_counter() -> None:

    _application()

    window = MainWindow()

    assert window.session_counter_text == "Sesión: 0 CALL | 0 PUT | 0 total"
    assert window.session_call_count == 0
    assert window.session_put_count == 0
    assert window.session_total_count == 0


def test_main_window_counts_confirmed_call_signal_in_session() -> None:

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
        operational_summary_label=(
            "Resumen operativo: ENTRADA CALL confirmada — revisar gestión "
            "de riesgo antes de operar manualmente."
        ),
    )

    window.update_signal(
        view_model=view_model,
    )

    assert window.session_counter_text == "Sesión: 1 CALL | 0 PUT | 1 total"
    assert window.session_call_count == 1
    assert window.session_put_count == 0
    assert window.session_total_count == 1


def test_main_window_counts_confirmed_put_signal_in_session() -> None:

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
        operational_summary_label=(
            "Resumen operativo: ENTRADA PUT confirmada — revisar gestión "
            "de riesgo antes de operar manualmente."
        ),
    )

    window.update_signal(
        view_model=view_model,
    )

    assert window.session_counter_text == "Sesión: 0 CALL | 1 PUT | 1 total"
    assert window.session_call_count == 0
    assert window.session_put_count == 1
    assert window.session_total_count == 1


def test_main_window_does_not_count_non_actionable_signal_in_session() -> None:

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
        operational_summary_label="Resumen operativo: ESPERAR",
    )

    window.update_signal(
        view_model=view_model,
    )

    assert window.session_counter_text == "Sesión: 0 CALL | 0 PUT | 0 total"
    assert window.session_total_count == 0


def test_main_window_does_not_count_same_signal_twice_in_session() -> None:

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
        operational_summary_label=(
            "Resumen operativo: ENTRADA PUT confirmada — revisar gestión "
            "de riesgo antes de operar manualmente."
        ),
    )

    window.update_signal(
        view_model=view_model,
    )
    window.update_signal(
        view_model=view_model,
    )

    assert window.session_counter_text == "Sesión: 0 CALL | 1 PUT | 1 total"
    assert window.session_total_count == 1


def test_main_window_keeps_session_counter_visible_in_compact_mode() -> None:

    _application()

    window = MainWindow()

    window._compact_mode_button.click()

    assert window.is_compact_mode_enabled is True
    assert window.session_counter_visible is True


def test_main_window_has_reset_session_button() -> None:

    _application()

    window = MainWindow()

    assert window.reset_session_button_text == "Reiniciar sesión"


def test_main_window_reset_session_counter_clears_session_counts() -> None:

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
        operational_summary_label=(
            "Resumen operativo: ENTRADA PUT confirmada — revisar gestión "
            "de riesgo antes de operar manualmente."
        ),
    )

    window.update_signal(
        view_model=view_model,
    )

    assert window.session_counter_text == "Sesión: 0 CALL | 1 PUT | 1 total"

    window.reset_session_counter()

    assert window.session_counter_text == "Sesión: 0 CALL | 0 PUT | 0 total"
    assert window.session_call_count == 0
    assert window.session_put_count == 0
    assert window.session_total_count == 0

    window.update_signal(
        view_model=view_model,
    )

    assert window.session_counter_text == "Sesión: 0 CALL | 1 PUT | 1 total"


def test_main_window_reset_session_button_does_not_clear_signal_history() -> None:

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
        operational_summary_label=(
            "Resumen operativo: ENTRADA CALL confirmada — revisar gestión "
            "de riesgo antes de operar manualmente."
        ),
    )

    window.update_signal(
        view_model=view_model,
    )

    assert window.signal_history_count == 1
    assert window.session_total_count == 1

    _button(
        window=window,
        object_name="reset_session_button",
    ).click()

    assert window.signal_history_count == 1
    assert window.session_total_count == 0
    assert window.session_counter_text == "Sesión: 0 CALL | 0 PUT | 0 total"


def test_main_window_keeps_reset_session_button_visible_in_compact_mode() -> None:

    _application()

    window = MainWindow()

    window._compact_mode_button.click()

    assert window.is_compact_mode_enabled is True
    assert window.reset_session_button_visible is True


def test_main_window_displays_initial_session_risk() -> None:

    _application()

    window = MainWindow()

    assert window.session_risk_text == (
        "Riesgo sesión: OK | Señales confirmadas: 0/12 | "
        "Recordatorio: detener si acumulas 3 pérdidas manuales"
    )
    assert window.session_risk_visible is True
    assert "#374151" in window.session_risk_style


def test_main_window_updates_session_risk_to_warning_near_limit() -> None:

    _application()

    window = MainWindow()

    for index in range(10):
        view_model = SignalRecordViewModel(
            direction_label="CALL",
            strength_label="ALTA",
            reason="CALL setup confirmed.",
            source="test_source",
            created_at_label=f"2026-01-01 10:30:{index:02d}",
            is_actionable=True,
            css_class="signal-call",
            operational_summary_label=(
                "Resumen operativo: ENTRADA CALL confirmada — revisar gestión "
                "de riesgo antes de operar manualmente."
            ),
        )

        window.update_signal(
            view_model=view_model,
        )

    assert window.session_total_count == 10
    assert window.session_risk_text == (
        "Riesgo sesión: ATENCIÓN | Señales confirmadas: 10/12 | "
        "Considera reducir operaciones"
    )
    assert "#b45309" in window.session_risk_style


def test_main_window_updates_session_risk_to_limit_when_limit_is_reached() -> None:

    _application()

    window = MainWindow()

    for index in range(12):
        view_model = SignalRecordViewModel(
            direction_label="PUT",
            strength_label="ALTA",
            reason="PUT setup confirmed.",
            source="test_source",
            created_at_label=f"2026-01-01 10:31:{index:02d}",
            is_actionable=True,
            css_class="signal-put",
            operational_summary_label=(
                "Resumen operativo: ENTRADA PUT confirmada — revisar gestión "
                "de riesgo antes de operar manualmente."
            ),
        )

        window.update_signal(
            view_model=view_model,
        )

    assert window.session_total_count == 12
    assert window.session_risk_text == (
        "Riesgo sesión: LÍMITE ALCANZADO | Señales confirmadas: 12/12 | "
        "No buscar más entradas en esta sesión"
    )
    assert "#d93025" in window.session_risk_style


def test_main_window_reset_session_counter_restores_session_risk() -> None:

    _application()

    window = MainWindow()

    for index in range(10):
        view_model = SignalRecordViewModel(
            direction_label="CALL",
            strength_label="ALTA",
            reason="CALL setup confirmed.",
            source="test_source",
            created_at_label=f"2026-01-01 10:32:{index:02d}",
            is_actionable=True,
            css_class="signal-call",
            operational_summary_label=(
                "Resumen operativo: ENTRADA CALL confirmada — revisar gestión "
                "de riesgo antes de operar manualmente."
            ),
        )

        window.update_signal(
            view_model=view_model,
        )

    assert window.session_total_count == 10
    assert "ATENCIÓN" in window.session_risk_text

    window.reset_session_counter()

    assert window.session_total_count == 0
    assert window.session_risk_text == (
        "Riesgo sesión: OK | Señales confirmadas: 0/12 | "
        "Recordatorio: detener si acumulas 3 pérdidas manuales"
    )


def test_main_window_keeps_session_risk_visible_in_compact_mode() -> None:

    _application()

    window = MainWindow()

    window._compact_mode_button.click()

    assert window.is_compact_mode_enabled is True
    assert window.session_risk_visible is True


def test_main_window_hides_session_pause_alert_by_default() -> None:

    _application()

    window = MainWindow()

    assert window.session_pause_alert_visible is False
    assert window.session_pause_alert_text == ""


def test_main_window_shows_session_pause_alert_when_limit_is_reached() -> None:

    _application()

    window = MainWindow()

    for index in range(12):
        view_model = SignalRecordViewModel(
            direction_label="PUT",
            strength_label="ALTA",
            reason="PUT setup confirmed.",
            source="test_source",
            created_at_label=f"2026-01-01 10:40:{index:02d}",
            is_actionable=True,
            css_class="signal-put",
            operational_summary_label=(
                "Resumen operativo: ENTRADA PUT confirmada — revisar gestión "
                "de riesgo antes de operar manualmente."
            ),
        )

        window.update_signal(
            view_model=view_model,
        )

    assert window.session_total_count == 12
    assert window.session_pause_alert_visible is True
    assert window.session_pause_alert_text == (
        "PAUSA RECOMENDADA\n"
        "Límite de señales alcanzado\n"
        "No buscar más entradas en esta sesión"
    )
    assert "#d93025" in window.session_pause_alert_style


def test_main_window_reset_session_counter_hides_session_pause_alert() -> None:

    _application()

    window = MainWindow()

    for index in range(12):
        view_model = SignalRecordViewModel(
            direction_label="CALL",
            strength_label="ALTA",
            reason="CALL setup confirmed.",
            source="test_source",
            created_at_label=f"2026-01-01 10:41:{index:02d}",
            is_actionable=True,
            css_class="signal-call",
            operational_summary_label=(
                "Resumen operativo: ENTRADA CALL confirmada — revisar gestión "
                "de riesgo antes de operar manualmente."
            ),
        )

        window.update_signal(
            view_model=view_model,
        )

    assert window.session_pause_alert_visible is True

    window.reset_session_counter()

    assert window.session_total_count == 0
    assert window.session_pause_alert_visible is False
    assert window.session_pause_alert_text == ""


def test_main_window_keeps_session_pause_alert_visible_in_compact_mode_when_limit_is_reached() -> None:

    _application()

    window = MainWindow()

    for index in range(12):
        view_model = SignalRecordViewModel(
            direction_label="PUT",
            strength_label="ALTA",
            reason="PUT setup confirmed.",
            source="test_source",
            created_at_label=f"2026-01-01 10:42:{index:02d}",
            is_actionable=True,
            css_class="signal-put",
            operational_summary_label=(
                "Resumen operativo: ENTRADA PUT confirmada — revisar gestión "
                "de riesgo antes de operar manualmente."
            ),
        )

        window.update_signal(
            view_model=view_model,
        )

    window._compact_mode_button.click()

    assert window.is_compact_mode_enabled is True
    assert window.session_pause_alert_visible is True


def test_main_window_uses_compact_session_risk_text_in_compact_mode() -> None:

    _application()

    window = MainWindow()

    window._compact_mode_button.click()

    assert window.is_compact_mode_enabled is True
    assert window.session_risk_text == "Riesgo: OK 0/12"


def test_main_window_restores_full_session_risk_text_when_leaving_compact_mode() -> None:

    _application()

    window = MainWindow()

    window._compact_mode_button.click()
    window._compact_mode_button.click()

    assert window.is_compact_mode_enabled is False
    assert window.session_risk_text == (
        "Riesgo sesión: OK | Señales confirmadas: 0/12 | "
        "Recordatorio: detener si acumulas 3 pérdidas manuales"
    )


def test_main_window_uses_compact_warning_session_risk_text() -> None:

    _application()

    window = MainWindow()

    for index in range(10):
        view_model = SignalRecordViewModel(
            direction_label="CALL",
            strength_label="ALTA",
            reason="CALL setup confirmed.",
            source="test_source",
            created_at_label=f"2026-01-01 10:50:{index:02d}",
            is_actionable=True,
            css_class="signal-call",
            operational_summary_label=(
                "Resumen operativo: ENTRADA CALL confirmada — revisar gestión "
                "de riesgo antes de operar manualmente."
            ),
        )

        window.update_signal(
            view_model=view_model,
        )

    window._compact_mode_button.click()

    assert window.is_compact_mode_enabled is True
    assert window.session_risk_text == "Riesgo: ATENCIÓN 10/12"


def test_main_window_uses_compact_limit_session_risk_text() -> None:

    _application()

    window = MainWindow()

    for index in range(12):
        view_model = SignalRecordViewModel(
            direction_label="PUT",
            strength_label="ALTA",
            reason="PUT setup confirmed.",
            source="test_source",
            created_at_label=f"2026-01-01 10:51:{index:02d}",
            is_actionable=True,
            css_class="signal-put",
            operational_summary_label=(
                "Resumen operativo: ENTRADA PUT confirmada — revisar gestión "
                "de riesgo antes de operar manualmente."
            ),
        )

        window.update_signal(
            view_model=view_model,
        )

    window._compact_mode_button.click()

    assert window.is_compact_mode_enabled is True
    assert window.session_risk_text == "Riesgo: LÍMITE 12/12"
    assert window.session_pause_alert_visible is True


def test_main_window_starts_with_voice_enabled() -> None:

    _application()

    window = MainWindow()

    assert window.voice_enabled is True
    assert window.voice_toggle_button_checked is True
    assert window.voice_toggle_button_text == "Voz activada"
    assert window.test_voice_button_text == "Probar voz"
    assert window.test_voice_button_enabled is True


def test_main_window_voice_toggle_notifies_callback() -> None:

    _application()

    changes: list[bool] = []

    window = MainWindow(
        on_voice_enabled_changed=changes.append,
    )

    _button(
        window=window,
        object_name="voice_toggle_button",
    ).click()

    assert window.voice_enabled is False
    assert window.voice_toggle_button_checked is False
    assert window.voice_toggle_button_text == "Voz desactivada"
    assert window.test_voice_button_enabled is False
    assert changes == [
        False,
    ]

    _button(
        window=window,
        object_name="voice_toggle_button",
    ).click()

    assert window.voice_enabled is True
    assert window.voice_toggle_button_checked is True
    assert window.voice_toggle_button_text == "Voz activada"
    assert window.test_voice_button_enabled is True
    assert changes == [
        False,
        True,
    ]


def test_main_window_test_voice_button_calls_callback() -> None:

    _application()

    callback = CallbackSpy()

    window = MainWindow(
        on_test_voice_requested=callback,
    )

    _button(
        window=window,
        object_name="test_voice_button",
    ).click()

    assert callback.calls == 1


def test_main_window_disabled_voice_prevents_test_callback() -> None:

    _application()

    callback = CallbackSpy()

    window = MainWindow(
        on_test_voice_requested=callback,
    )

    _button(
        window=window,
        object_name="voice_toggle_button",
    ).click()
    _button(
        window=window,
        object_name="test_voice_button",
    ).click()

    assert window.voice_enabled is False
    assert window.test_voice_button_enabled is False
    assert callback.calls == 0


def test_main_window_restores_saved_voice_preference(
    tmp_path,
) -> None:

    _application()

    settings = _temporary_settings(
        tmp_path,
    )
    changes: list[bool] = []

    settings.beginGroup(
        MainWindow.SETTINGS_GROUP,
    )
    settings.setValue(
        MainWindow.SETTING_VOICE_ENABLED,
        False,
    )
    settings.endGroup()
    settings.sync()

    window = MainWindow(
        settings=settings,
        restore_window_preferences=True,
        on_voice_enabled_changed=changes.append,
    )

    assert window.voice_enabled is False
    assert window.voice_toggle_button_text == "Voz desactivada"
    assert window.test_voice_button_enabled is False
    assert changes == [
        False,
    ]


def test_main_window_saves_voice_preference(
    tmp_path,
) -> None:

    _application()

    settings = _temporary_settings(
        tmp_path,
    )

    window = MainWindow(
        settings=settings,
        restore_window_preferences=True,
    )

    _button(
        window=window,
        object_name="voice_toggle_button",
    ).click()

    settings.beginGroup(
        MainWindow.SETTINGS_GROUP,
    )

    assert settings.value(
        MainWindow.SETTING_VOICE_ENABLED,
        type=bool,
    ) is False

    settings.endGroup()


def test_main_window_keeps_voice_controls_visible_in_compact_mode() -> None:

    _application()

    window = MainWindow()

    window._compact_mode_button.click()

    assert window.is_compact_mode_enabled is True
    assert window.voice_toggle_button_visible is True
    assert window.test_voice_button_visible is True


def test_main_window_displays_initial_manual_results() -> None:

    _application()

    window = MainWindow()

    assert window.session_result_text == (
        "Resultados: 0 ganadas | 0 perdidas | "
        "Tasa observada: - | Racha de pérdidas: 0/3"
    )
    assert window.session_result_wins == 0
    assert window.session_result_losses == 0
    assert window.session_result_total == 0
    assert window.session_consecutive_losses == 0
    assert window.session_result_pause_alert_visible is False


def test_main_window_disables_result_buttons_without_confirmed_signal() -> None:

    _application()

    window = MainWindow()

    assert window.register_win_button_enabled is False
    assert window.register_loss_button_enabled is False
    assert window.undo_result_button_enabled is False


def test_main_window_enables_result_buttons_after_confirmed_signal() -> None:

    _application()

    window = MainWindow()

    window.update_signal(
        view_model=_confirmed_signal(
            index=0,
        ),
    )

    assert window.session_total_count == 1
    assert window.register_win_button_enabled is True
    assert window.register_loss_button_enabled is True
    assert window.undo_result_button_enabled is False


def test_main_window_registers_manual_win() -> None:

    _application()

    window = MainWindow()

    window.update_signal(
        view_model=_confirmed_signal(
            index=0,
        ),
    )

    _button(
        window=window,
        object_name="register_win_button",
    ).click()

    assert window.session_result_wins == 1
    assert window.session_result_losses == 0
    assert window.session_result_total == 1
    assert window.session_win_rate_percentage == 100.0
    assert window.session_result_text == (
        "Resultados: 1 ganadas | 0 perdidas | "
        "Tasa observada: 100,0 % | Racha de pérdidas: 0/3"
    )
    assert window.register_win_button_enabled is False
    assert window.register_loss_button_enabled is False
    assert window.undo_result_button_enabled is True


def test_main_window_registers_manual_loss() -> None:

    _application()

    window = MainWindow()

    window.update_signal(
        view_model=_confirmed_signal(
            index=0,
            direction="PUT",
        ),
    )

    _button(
        window=window,
        object_name="register_loss_button",
    ).click()

    assert window.session_result_wins == 0
    assert window.session_result_losses == 1
    assert window.session_result_total == 1
    assert window.session_consecutive_losses == 1
    assert window.session_win_rate_percentage == 0.0


def test_main_window_prevents_extra_result_without_new_signal() -> None:

    _application()

    window = MainWindow()

    window.update_signal(
        view_model=_confirmed_signal(
            index=0,
        ),
    )

    win_button = _button(
        window=window,
        object_name="register_win_button",
    )

    win_button.click()
    win_button.click()

    assert window.session_total_count == 1
    assert window.session_result_total == 1
    assert window.session_result_wins == 1


def test_main_window_reenables_result_buttons_after_new_signal() -> None:

    _application()

    window = MainWindow()

    window.update_signal(
        view_model=_confirmed_signal(
            index=0,
        ),
    )

    _button(
        window=window,
        object_name="register_win_button",
    ).click()

    assert window.register_win_button_enabled is False

    window.update_signal(
        view_model=_confirmed_signal(
            index=1,
            direction="PUT",
        ),
    )

    assert window.session_total_count == 2
    assert window.session_result_total == 1
    assert window.register_win_button_enabled is True
    assert window.register_loss_button_enabled is True


def test_main_window_undoes_last_manual_result() -> None:

    _application()

    window = MainWindow()

    window.update_signal(
        view_model=_confirmed_signal(
            index=0,
        ),
    )

    _button(
        window=window,
        object_name="register_loss_button",
    ).click()
    _button(
        window=window,
        object_name="undo_result_button",
    ).click()

    assert window.session_result_total == 0
    assert window.session_result_losses == 0
    assert window.session_consecutive_losses == 0
    assert window.register_win_button_enabled is True
    assert window.register_loss_button_enabled is True
    assert window.undo_result_button_enabled is False


def test_main_window_shows_pause_alert_after_three_manual_losses() -> None:

    _application()

    window = MainWindow()

    for index in range(3):
        window.update_signal(
            view_model=_confirmed_signal(
                index=index,
                direction="PUT",
            ),
        )

        _button(
            window=window,
            object_name="register_loss_button",
        ).click()

    assert window.session_result_losses == 3
    assert window.session_consecutive_losses == 3
    assert window.session_result_pause_alert_visible is True
    assert window.session_result_pause_alert_text == (
        "PAUSA RECOMENDADA\n"
        "Se alcanzaron 3 pérdidas consecutivas\n"
        "Detén la sesión y revisa las operaciones"
    )
    assert "#d93025" in window.session_result_pause_alert_style


def test_main_window_hides_loss_pause_alert_after_manual_win() -> None:

    _application()

    window = MainWindow()

    for index in range(3):
        window.update_signal(
            view_model=_confirmed_signal(
                index=index,
                direction="PUT",
            ),
        )

        _button(
            window=window,
            object_name="register_loss_button",
        ).click()

    assert window.session_result_pause_alert_visible is True

    window.update_signal(
        view_model=_confirmed_signal(
            index=3,
            direction="CALL",
        ),
    )

    _button(
        window=window,
        object_name="register_win_button",
    ).click()

    assert window.session_consecutive_losses == 0
    assert window.session_result_pause_alert_visible is False
    assert window.session_result_pause_alert_text == ""


def test_main_window_reset_session_clears_signals_and_results() -> None:

    _application()

    window = MainWindow()

    window.update_signal(
        view_model=_confirmed_signal(
            index=0,
        ),
    )
    _button(
        window=window,
        object_name="register_win_button",
    ).click()

    window.update_signal(
        view_model=_confirmed_signal(
            index=1,
            direction="PUT",
        ),
    )
    _button(
        window=window,
        object_name="register_loss_button",
    ).click()

    assert window.session_total_count == 2
    assert window.session_result_total == 2

    _button(
        window=window,
        object_name="reset_session_button",
    ).click()

    assert window.session_total_count == 0
    assert window.session_result_total == 0
    assert window.session_result_wins == 0
    assert window.session_result_losses == 0
    assert window.session_consecutive_losses == 0
    assert window.session_result_pause_alert_visible is False
    assert window.register_win_button_enabled is False
    assert window.register_loss_button_enabled is False
    assert window.undo_result_button_enabled is False


def test_main_window_uses_compact_result_view_and_keeps_controls_visible() -> None:

    _application()

    window = MainWindow()

    window.update_signal(
        view_model=_confirmed_signal(
            index=0,
        ),
    )
    _button(
        window=window,
        object_name="register_win_button",
    ).click()

    window._compact_mode_button.click()

    assert window.is_compact_mode_enabled is True
    assert window.session_result_text == (
        "Resultados: 1G | 0P | 100,0 % | Racha: 0/3"
    )
    assert window.session_result_visible is True
    assert window.register_win_button_visible is True
    assert window.register_loss_button_visible is True
    assert window.undo_result_button_visible is True


def test_main_window_reports_when_signal_is_counted_as_new() -> None:

    _application()

    window = MainWindow()
    signal = _confirmed_signal(
        index=0,
    )

    first_result = window.update_signal(
        view_model=signal,
    )
    duplicate_result = window.update_signal(
        view_model=signal,
    )

    assert first_result is True
    assert duplicate_result is False
    assert window.session_total_count == 1


def test_main_window_notifies_successful_manual_result_callback() -> None:

    _application()

    received_results = []

    window = MainWindow(
        on_session_result_registered=lambda result: (
            received_results.append(result)
            or True
        ),
    )

    window.update_signal(
        view_model=_confirmed_signal(
            index=0,
        ),
    )
    window.register_session_win()

    assert received_results == [
        SessionResult.WIN,
    ]
    assert window.session_result_wins == 1


def test_main_window_does_not_change_result_when_callback_fails() -> None:

    _application()

    window = MainWindow(
        on_session_result_registered=lambda result: False,
    )

    window.update_signal(
        view_model=_confirmed_signal(
            index=0,
        ),
    )
    window.register_session_loss()

    assert window.session_result_total == 0
    assert window.register_loss_button_enabled is True


def test_main_window_notifies_undo_and_reset_callbacks() -> None:

    _application()

    undo_calls = []
    reset_calls = []

    window = MainWindow(
        on_session_result_registered=lambda result: True,
        on_session_result_undone=lambda: (
            undo_calls.append(True)
            or True
        ),
        on_session_reset_requested=lambda: reset_calls.append(True),
    )

    window.update_signal(
        view_model=_confirmed_signal(
            index=0,
        ),
    )
    window.register_session_win()
    window.undo_last_session_result()
    window.reset_session()

    assert undo_calls == [
        True,
    ]
    assert reset_calls == [
        True,
    ]


def test_main_window_enables_and_disables_evidence_mode() -> None:

    _application()

    requested_states: list[bool] = []

    window = MainWindow(
        on_evidence_mode_changed=lambda enabled: (
            requested_states.append(enabled)
            or True
        ),
    )

    button = _button(
        window=window,
        object_name="evidence_mode_button",
    )

    button.click()

    assert window.evidence_mode_enabled is True
    assert window.evidence_mode_button_checked is True
    assert (
        window.evidence_mode_button_text
        == "Restaurar protección"
    )

    button.click()

    assert window.evidence_mode_enabled is False
    assert window.evidence_mode_button_checked is False
    assert window.evidence_mode_button_text == "Modo evidencia"
    assert requested_states == [
        True,
        False,
    ]


def test_main_window_reverts_evidence_button_when_callback_fails() -> None:

    _application()

    window = MainWindow(
        on_evidence_mode_changed=lambda enabled: False,
    )

    _button(
        window=window,
        object_name="evidence_mode_button",
    ).click()

    assert window.evidence_mode_enabled is False
    assert window.evidence_mode_button_checked is False
    assert window.evidence_mode_button_text == "Modo evidencia"


def test_main_window_keeps_evidence_mode_button_visible_in_compact_mode() -> None:

    _application()

    window = MainWindow()

    window._compact_mode_button.click()

    assert window.is_compact_mode_enabled is True
    assert window.evidence_mode_button_visible is True