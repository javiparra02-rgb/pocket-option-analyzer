from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QTextCursor, QTextOption
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pocket_option_analyzer.presentation.signals import (
    ConfirmationChecklistPresenter,
    EntryAlertPresenter,
    OperationalSummaryPresenter,
    SessionResult,
    SessionResultPresenter,
    SessionResultTracker,
    SessionRiskPresenter,
    SessionSignalCounter,
    SignalRecordViewModel,
)

WindowAction = Callable[[], None]
BooleanWindowAction = Callable[[bool], None]
SessionResultWindowAction = Callable[[SessionResult], bool]
ConfirmedResultWindowAction = Callable[[], bool]


class MainWindow(QMainWindow):
    """
    Ventana principal de la aplicación.

    No ejecuta análisis por sí misma.
    No captura pantalla.
    No interactúa con Pocket Option.

    Solo representa el estado visual de la GUI y delega acciones
    mediante callbacks.
    """

    CAPTURE_NOTE = (
        "Nota: no cubras el gráfico de Pocket Option con esta ventana. "
        "El análisis usa los píxeles visibles en pantalla."
    )

    MAX_SIGNAL_HISTORY_ITEMS = 50

    FULL_WINDOW_WIDTH = 560
    FULL_WINDOW_HEIGHT = 520

    FULL_MIN_WIDTH = 460
    FULL_MIN_HEIGHT = 360

    COMPACT_WINDOW_WIDTH = 500
    COMPACT_WINDOW_HEIGHT = 240

    COMPACT_MIN_WIDTH = 420
    COMPACT_MIN_HEIGHT = 220

    FULL_LAYOUT_MARGIN = 12
    COMPACT_LAYOUT_MARGIN = 8

    FULL_LAYOUT_SPACING = 8
    COMPACT_LAYOUT_SPACING = 4

    SAFE_WINDOW_MARGIN = 24

    OPERATIONAL_SUMMARY_CALL_STYLE = (
        "font-weight: bold; "
        "color: #0f9d58; "
        "background-color: #eefaf3; "
        "border: 1px solid #0f9d58; "
        "border-radius: 4px; "
        "padding: 4px;"
    )

    OPERATIONAL_SUMMARY_PUT_STYLE = (
        "font-weight: bold; "
        "color: #d93025; "
        "background-color: #fff0f0; "
        "border: 1px solid #d93025; "
        "border-radius: 4px; "
        "padding: 4px;"
    )

    OPERATIONAL_SUMMARY_NEUTRAL_STYLE = (
        "font-weight: bold; "
        "color: #5f6368; "
        "background-color: #f8f9fa; "
        "border: 1px solid #9aa0a6; "
        "border-radius: 4px; "
        "padding: 4px;"
    )

    CONFIRMATION_CHECKLIST_NEUTRAL_STYLE = (
        "font-weight: bold; "
        "color: #374151; "
        "background-color: #f8f9fa; "
        "border: 1px solid #c7cdd4; "
        "border-radius: 4px; "
        "padding: 4px;"
    )

    CONFIRMATION_CHECKLIST_CALL_STYLE = (
        "font-weight: bold; "
        "color: #0f9d58; "
        "background-color: #eefaf3; "
        "border: 1px solid #0f9d58; "
        "border-radius: 4px; "
        "padding: 4px;"
    )

    CONFIRMATION_CHECKLIST_PUT_STYLE = (
        "font-weight: bold; "
        "color: #d93025; "
        "background-color: #fff0f0; "
        "border: 1px solid #d93025; "
        "border-radius: 4px; "
        "padding: 4px;"
    )

    ENTRY_ALERT_CALL_STYLE = (
        "font-weight: bold; "
        "font-size: 16px; "
        "color: #0f9d58; "
        "background-color: #dff5e8; "
        "border: 2px solid #0f9d58; "
        "border-radius: 6px; "
        "padding: 8px;"
    )

    ENTRY_ALERT_PUT_STYLE = (
        "font-weight: bold; "
        "font-size: 16px; "
        "color: #d93025; "
        "background-color: #ffe5e5; "
        "border: 2px solid #d93025; "
        "border-radius: 6px; "
        "padding: 8px;"
    )

    SESSION_COUNTER_STYLE = (
        "font-weight: bold; "
        "color: #374151; "
        "background-color: #f8f9fa; "
        "border: 1px solid #c7cdd4; "
        "border-radius: 4px; "
        "padding: 4px;"
    )

    SESSION_RESULT_STYLE = (
        "font-weight: bold; "
        "color: #374151; "
        "background-color: #f8f9fa; "
        "border: 1px solid #c7cdd4; "
        "border-radius: 4px; "
        "padding: 4px;"
    )

    SESSION_RESULT_PAUSE_ALERT_STYLE = (
        "font-weight: bold; "
        "font-size: 16px; "
        "color: #d93025; "
        "background-color: #fff0f0; "
        "border: 2px solid #d93025; "
        "border-radius: 6px; "
        "padding: 8px;"
    )

    SESSION_RISK_OK_STYLE = (
        "font-weight: bold; "
        "color: #374151; "
        "background-color: #f8f9fa; "
        "border: 1px solid #c7cdd4; "
        "border-radius: 4px; "
        "padding: 4px;"
    )

    SESSION_RISK_WARNING_STYLE = (
        "font-weight: bold; "
        "color: #b45309; "
        "background-color: #fff7ed; "
        "border: 1px solid #f59e0b; "
        "border-radius: 4px; "
        "padding: 4px;"
    )

    SESSION_RISK_LIMIT_STYLE = (
        "font-weight: bold; "
        "color: #d93025; "
        "background-color: #fff0f0; "
        "border: 1px solid #d93025; "
        "border-radius: 4px; "
        "padding: 4px;"
    )

    SESSION_PAUSE_ALERT_STYLE = (
        "font-weight: bold; "
        "font-size: 16px; "
        "color: #d93025; "
        "background-color: #fff0f0; "
        "border: 2px solid #d93025; "
        "border-radius: 6px; "
        "padding: 8px;"
    )

    SETTINGS_ORGANIZATION = "PocketOptionAnalyzer"
    SETTINGS_APPLICATION = "PocketOptionAnalyzer"

    SETTINGS_GROUP = "main_window"
    SETTING_COMPACT_MODE = "compact_mode"
    SETTING_X = "x"
    SETTING_Y = "y"
    SETTING_WIDTH = "width"
    SETTING_HEIGHT = "height"

    SETTING_VOICE_ENABLED = "voice_enabled"

    def __init__(
        self,
        on_start_requested: WindowAction | None = None,
        on_stop_requested: WindowAction | None = None,
        on_run_once_requested: WindowAction | None = None,
        on_voice_enabled_changed: BooleanWindowAction | None = None,
        on_test_voice_requested: WindowAction | None = None,
        on_session_result_registered: SessionResultWindowAction | None = None,
        on_session_result_undone: ConfirmedResultWindowAction | None = None,
        on_session_reset_requested: WindowAction | None = None,
        settings: QSettings | None = None,
        restore_window_preferences: bool = False,
    ) -> None:
        super().__init__()

        self._on_start_requested = on_start_requested
        self._on_stop_requested = on_stop_requested
        self._on_run_once_requested = on_run_once_requested
        self._on_voice_enabled_changed = on_voice_enabled_changed
        self._on_test_voice_requested = on_test_voice_requested
        self._voice_enabled = True
        self._on_session_result_registered = on_session_result_registered
        self._on_session_result_undone = on_session_result_undone
        self._on_session_reset_requested = on_session_reset_requested
        self._settings = settings or QSettings(
            self.SETTINGS_ORGANIZATION,
            self.SETTINGS_APPLICATION,
        )
        self._restore_window_preferences_enabled = restore_window_preferences
        self._confirmation_checklist_presenter = ConfirmationChecklistPresenter()
        self._entry_alert_presenter = EntryAlertPresenter()
        self._operational_summary_presenter = OperationalSummaryPresenter()
        self._session_signal_counter = SessionSignalCounter()
        self._session_risk_presenter = SessionRiskPresenter()
        self._session_result_tracker = SessionResultTracker()
        self._session_result_presenter = SessionResultPresenter()

        self.setWindowTitle(
            "Pocket Option Analyzer",
        )
        self.resize(
            self.FULL_WINDOW_WIDTH,
            self.FULL_WINDOW_HEIGHT,
        )
        self.setMinimumSize(
            self.FULL_MIN_WIDTH,
            self.FULL_MIN_HEIGHT,
        )

        self._history_label = QLabel(
            "Historial de señales:",
        )

        self._history_list = QListWidget()
        self._history_list.setMaximumHeight(
            90,
        )
        self._history_list.setMinimumHeight(
            70,
        )
        self._history_list.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self._clear_history_button = QPushButton(
            "Limpiar historial",
        )
        self._clear_history_button.setObjectName(
            "clear_history_button",
        )

        self._status_label = QLabel(
            "Estado: detenido",
        )
        self._error_label = QLabel(
            "Error: -",
        )

        self._capture_note_label = QLabel(
            self.CAPTURE_NOTE,
        )
        self._capture_note_label.setWordWrap(
            True,
        )
        self._capture_note_label.setStyleSheet(
            "color: #5f6368; font-style: italic;"
        )
        
        self._entry_alert_label = QLabel(
            "",
        )
        self._entry_alert_label.setWordWrap(
            True,
        )
        self._entry_alert_label.setHidden(
            True,
        )
        self._direction_label = QLabel(
            "Señal: SIN SEÑAL",
        )
        self._strength_label = QLabel(
            "Fuerza: NINGUNA",
        )
        self._operational_summary_label = QLabel(
            "Resumen operativo: ESPERAR",
        )
        self._operational_summary_label.setWordWrap(
            True,
        )
        self._confirmation_checklist_label = QLabel(
            "Visual: ❌ | EMA: ❌ | RSI: ❌ | Stoch: ❌ | Entrada: ESPERAR",
        )
        self._session_counter_label = QLabel(
            "Sesión: 0 CALL | 0 PUT | 0 total",
        )
        initial_session_risk = self._session_risk_presenter.present(
            total_confirmed_signals=0,
        )
        self._session_risk_label = QLabel(
            initial_session_risk.text,
        )
        self._session_risk_label.setWordWrap(
            True,
        )
        self._session_risk_label.setStyleSheet(
            self.SESSION_RISK_OK_STYLE,
        )
        self._session_pause_alert_label = QLabel(
            "",
        )
        self._session_pause_alert_label.setWordWrap(
            True,
        )
        self._session_pause_alert_label.setStyleSheet(
            self.SESSION_PAUSE_ALERT_STYLE,
        )
        self._session_pause_alert_label.setHidden(
            True,
        )
        initial_session_result = self._session_result_presenter.present(
            snapshot=self._session_result_tracker.snapshot(),
        )

        self._session_result_label = QLabel(
            initial_session_result.text,
        )
        self._session_result_label.setWordWrap(
            True,
        )
        self._session_result_label.setStyleSheet(
            self.SESSION_RESULT_STYLE,
        )

        self._session_result_pause_alert_label = QLabel(
            "",
        )
        self._session_result_pause_alert_label.setWordWrap(
            True,
        )
        self._session_result_pause_alert_label.setStyleSheet(
            self.SESSION_RESULT_PAUSE_ALERT_STYLE,
        )
        self._session_result_pause_alert_label.setHidden(
            True,
        )

        self._register_win_button = QPushButton(
            "Registrar ganada",
        )
        self._register_win_button.setObjectName(
            "register_win_button",
        )
        self._register_win_button.setEnabled(
            False,
        )

        self._register_loss_button = QPushButton(
            "Registrar perdida",
        )
        self._register_loss_button.setObjectName(
            "register_loss_button",
        )
        self._register_loss_button.setEnabled(
            False,
        )

        self._undo_result_button = QPushButton(
            "Deshacer resultado",
        )
        self._undo_result_button.setObjectName(
            "undo_result_button",
        )
        self._undo_result_button.setEnabled(
            False,
        )
        self._session_counter_label.setWordWrap(
            True,
        )
        self._session_counter_label.setStyleSheet(
            self.SESSION_COUNTER_STYLE,
        )
        self._reset_session_button = QPushButton(
            "Reiniciar sesión",
        )
        self._reset_session_button.setObjectName(
            "reset_session_button",
        )
        self._confirmation_checklist_label.setWordWrap(
            True,
        )
        self._confirmation_checklist_label.setStyleSheet(
            self.CONFIRMATION_CHECKLIST_NEUTRAL_STYLE,
        )
        self._operational_summary_label.setStyleSheet(
            self.OPERATIONAL_SUMMARY_NEUTRAL_STYLE,
        )
        self._visual_diagnostics_label = QLabel(
            "Diagnóstico visual: -",
        )
        self._visual_diagnostics_label.setWordWrap(
            True,
        )
        self._visual_diagnostics_label.setStyleSheet(
            "color: #3c4043;"
        )
        self._indicator_diagnostics_label = QLabel(
            "Diagnóstico de indicadores: -",
        )
        self._indicator_diagnostics_label.setWordWrap(
            True,
        )
        self._indicator_diagnostics_label.setStyleSheet(
            "color: #3c4043;"
        )

        self._reason_text = QTextEdit()
        self._reason_text.setReadOnly(
            True,
        )
        self._reason_text.setPlainText(
            "Motivo: -",
        )
        self._reason_text.setMinimumHeight(
            180,
        )
        self._reason_text.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._reason_text.setWordWrapMode(
            QTextOption.WrapMode.WordWrap,
        )

        self._source_label = QLabel(
            "Origen: -",
        )
        self._created_at_label = QLabel(
            "Fecha: -",
        )

        self._start_button = QPushButton(
            "Iniciar análisis",
        )
        self._start_button.setObjectName(
            "start_button",
        )

        self._stop_button = QPushButton(
            "Detener análisis",
        )
        self._stop_button.setObjectName(
            "stop_button",
        )

        self._run_once_button = QPushButton(
            "Analizar una vez",
        )
        self._run_once_button.setObjectName(
            "run_once_button",
        )

        self._compact_mode_button = QPushButton(
            "Modo compacto",
        )
        self._compact_mode_button.clicked.connect(
            self._toggle_compact_mode,
        )

        self._reset_view_button = QPushButton(
            "Restablecer vista",
        )
        self._reset_view_button.setObjectName(
            "reset_view_button",
        )

        self._voice_toggle_button = QPushButton(
            "Voz activada",
        )
        self._voice_toggle_button.setObjectName(
            "voice_toggle_button",
        )
        self._voice_toggle_button.setCheckable(
            True,
        )
        self._voice_toggle_button.setChecked(
            True,
        )

        self._test_voice_button = QPushButton(
            "Probar voz",
        )
        self._test_voice_button.setObjectName(
            "test_voice_button",
        )

        self._compact_mode_enabled = False

        self._setup_layout()
        self._connect_events()
        self._apply_signal_style(
            css_class="signal-neutral",
        )
        self.set_running_state(
            is_running=False,
        )
        self._refresh_session_result_ui()

        if self._restore_window_preferences_enabled:
            self._restore_window_preferences()

    @property
    def status_text(self) -> str:
        return self._status_label.text()

    @property
    def error_text(self) -> str:
        return self._error_label.text()

    @property
    def capture_note_text(self) -> str:
        return self._capture_note_label.text()

    @property
    def direction_text(self) -> str:
        return self._direction_label.text()

    @property
    def strength_text(self) -> str:
        return self._strength_label.text()

    @property
    def reason_text(self) -> str:
        return self._reason_text.toPlainText()

    @property
    def source_text(self) -> str:
        return self._source_label.text()

    @property
    def created_at_text(self) -> str:
        return self._created_at_label.text()

    @property
    def direction_style(self) -> str:
        return self._direction_label.styleSheet()

    @property
    def strength_style(self) -> str:
        return self._strength_label.styleSheet()
    
    @property
    def has_scrollable_content(self) -> bool:
        return isinstance(
            self.centralWidget(),
            QScrollArea,
        )

    @property
    def reason_style(self) -> str:
        return self._reason_text.styleSheet()

    @property
    def reason_scroll_position(self) -> int:
        return self._reason_text.verticalScrollBar().value()

    @property
    def reason_minimum_height(self) -> int:
        return self._reason_text.minimumHeight()

    @property
    def start_button_enabled(self) -> bool:
        return self._start_button.isEnabled()

    @property
    def stop_button_enabled(self) -> bool:
        return self._stop_button.isEnabled()

    @property
    def run_once_button_enabled(self) -> bool:
        return self._run_once_button.isEnabled()
    
    @property
    def clear_history_button_enabled(self) -> bool:
        return self._clear_history_button.isEnabled()
    
    @property
    def signal_history_texts(self) -> list[str]:
        return [
            self._history_list.item(index).text()
            for index in range(
                self._history_list.count(),
            )
        ]

    @property
    def max_signal_history_items(self) -> int:
        return self.MAX_SIGNAL_HISTORY_ITEMS
    
    @property
    def signal_history_count(self) -> int:
        return self._history_list.count()

    @property
    def latest_signal_history_text(self) -> str | None:
        if self._history_list.count() == 0:
            return None

        item = self._history_list.item(
            0,
        )

        return item.text()
    
    @property
    def signal_history_maximum_height(self) -> int:
        return self._history_list.maximumHeight()

    @property
    def operational_summary_text(self) -> str:
        return self._operational_summary_label.text()
    
    @property
    def operational_summary_style(self) -> str:
        return self._operational_summary_label.styleSheet()
    
    @property
    def visual_diagnostics_text(self) -> str:
        return self._visual_diagnostics_label.text()
    
    @property
    def indicator_diagnostics_text(self) -> str:
        return self._indicator_diagnostics_label.text()
    
    @property
    def compact_mode_button_text(self) -> str:
        return self._compact_mode_button.text()

    @property
    def reset_view_button_text(self) -> str:
        return self._reset_view_button.text()

    @property
    def is_compact_mode_enabled(self) -> bool:
        return self._compact_mode_enabled

    @property
    def visual_diagnostics_visible(self) -> bool:
        return not self._visual_diagnostics_label.isHidden()

    @property
    def indicator_diagnostics_visible(self) -> bool:
        return not self._indicator_diagnostics_label.isHidden()

    @property
    def signal_history_visible(self) -> bool:
        return not self._history_list.isHidden()

    @property
    def window_size(self) -> tuple[int, int]:
        return (
            self.width(),
            self.height(),
        )

    @property
    def minimum_window_size(self) -> tuple[int, int]:
        return (
            self.minimumWidth(),
            self.minimumHeight(),
        )

    @property
    def layout_spacing(self) -> int:
        return self._main_layout.spacing()
    
    @property
    def signal_label_visible(self) -> bool:
        return not self._direction_label.isHidden()

    @property
    def strength_label_visible(self) -> bool:
        return not self._strength_label.isHidden()

    @property
    def operational_summary_visible(self) -> bool:
        return not self._operational_summary_label.isHidden()
    
    @property
    def confirmation_checklist_text(self) -> str:
        return self._confirmation_checklist_label.text()

    @property
    def confirmation_checklist_visible(self) -> bool:
        return not self._confirmation_checklist_label.isHidden()

    @property
    def confirmation_checklist_style(self) -> str:
        return self._confirmation_checklist_label.styleSheet()

    @property
    def entry_alert_text(self) -> str:
        return self._entry_alert_label.text()

    @property
    def entry_alert_visible(self) -> bool:
        return not self._entry_alert_label.isHidden()

    @property
    def entry_alert_style(self) -> str:
        return self._entry_alert_label.styleSheet()
    
    @property
    def session_counter_text(self) -> str:
        return self._session_counter_label.text()

    @property
    def session_counter_visible(self) -> bool:
        return not self._session_counter_label.isHidden()

    @property
    def session_call_count(self) -> int:
        return self._session_signal_counter.call_count


    @property
    def session_put_count(self) -> int:
        return self._session_signal_counter.put_count


    @property
    def session_total_count(self) -> int:
        return self._session_signal_counter.total_count
    
    @property
    def reset_session_button_text(self) -> str:
        return self._reset_session_button.text()

    @property
    def reset_session_button_visible(self) -> bool:
        return not self._reset_session_button.isHidden()
    
    @property
    def session_risk_text(self) -> str:
        return self._session_risk_label.text()

    @property
    def session_risk_visible(self) -> bool:
        return not self._session_risk_label.isHidden()

    @property
    def session_risk_style(self) -> str:
        return self._session_risk_label.styleSheet()

    @property
    def session_pause_alert_text(self) -> str:
        return self._session_pause_alert_label.text()

    @property
    def session_pause_alert_visible(self) -> bool:
        return not self._session_pause_alert_label.isHidden()

    @property
    def session_pause_alert_style(self) -> str:
        return self._session_pause_alert_label.styleSheet()
    
    @property
    def voice_enabled(self) -> bool:
        return self._voice_enabled

    @property
    def voice_toggle_button_text(self) -> str:
        return self._voice_toggle_button.text()

    @property
    def voice_toggle_button_checked(self) -> bool:
        return self._voice_toggle_button.isChecked()

    @property
    def voice_toggle_button_visible(self) -> bool:
        return not self._voice_toggle_button.isHidden()

    @property
    def test_voice_button_text(self) -> str:
        return self._test_voice_button.text()

    @property
    def test_voice_button_enabled(self) -> bool:
        return self._test_voice_button.isEnabled()

    @property
    def test_voice_button_visible(self) -> bool:
        return not self._test_voice_button.isHidden()
    
    @property
    def session_result_text(self) -> str:
        return self._session_result_label.text()

    @property
    def session_result_visible(self) -> bool:
        return not self._session_result_label.isHidden()

    @property
    def session_result_style(self) -> str:
        return self._session_result_label.styleSheet()

    @property
    def session_result_wins(self) -> int:
        return self._session_result_tracker.wins

    @property
    def session_result_losses(self) -> int:
        return self._session_result_tracker.losses

    @property
    def session_result_total(self) -> int:
        return self._session_result_tracker.total

    @property
    def session_consecutive_losses(self) -> int:
        return self._session_result_tracker.consecutive_losses

    @property
    def session_win_rate_percentage(self) -> float | None:
        return self._session_result_tracker.win_rate_percentage

    @property
    def session_result_pause_alert_text(self) -> str:
        return self._session_result_pause_alert_label.text()

    @property
    def session_result_pause_alert_visible(self) -> bool:
        return not self._session_result_pause_alert_label.isHidden()

    @property
    def session_result_pause_alert_style(self) -> str:
        return self._session_result_pause_alert_label.styleSheet()

    @property
    def register_win_button_enabled(self) -> bool:
        return self._register_win_button.isEnabled()

    @property
    def register_loss_button_enabled(self) -> bool:
        return self._register_loss_button.isEnabled()

    @property
    def undo_result_button_enabled(self) -> bool:
        return self._undo_result_button.isEnabled()

    @property
    def register_win_button_visible(self) -> bool:
        return not self._register_win_button.isHidden()

    @property
    def register_loss_button_visible(self) -> bool:
        return not self._register_loss_button.isHidden()

    @property
    def undo_result_button_visible(self) -> bool:
        return not self._undo_result_button.isHidden()

    def set_running_state(
        self,
        is_running: bool,
    ) -> None:
        """
        Actualiza el estado visible del motor de análisis.
        """

        if is_running:
            self._status_label.setText(
                "Estado: ejecutando",
            )
        else:
            self._status_label.setText(
                "Estado: detenido",
            )

        self._apply_button_state(
            is_running=is_running,
        )

    def set_error_message(
        self,
        message: str | None,
    ) -> None:
        """
        Muestra o limpia el mensaje de error visible.
        """

        if message:
            self._error_label.setText(
                f"Error: {message}",
            )
            return

        self._error_label.setText(
            "Error: -",
        )

    def hide_for_capture(self) -> None:
        """
        Oculta temporalmente la ventana para no tapar el gráfico.

        Esto ayuda porque MSS captura los píxeles visibles en pantalla.
        """

        self.hide()
        QApplication.processEvents()

    def show_after_capture(self) -> None:
        """
        Vuelve a mostrar la ventana después de capturar.
        """

        self.show()
        self.raise_()
        QApplication.processEvents()

    def update_signal(
        self,
        view_model: SignalRecordViewModel,
    ) -> bool:
        """
        Actualiza la información visible de la última señal.
        """

        previous_session_total = self._session_signal_counter.total_count

        self._direction_label.setText(
            f"Señal: {view_model.direction_label}",
        )
        self._strength_label.setText(
            f"Fuerza: {view_model.strength_label}",
        )
        self._visual_diagnostics_label.setText(
            view_model.visual_diagnostics_label,
        )
        self._indicator_diagnostics_label.setText(
            view_model.indicator_diagnostics_label,
        )
        self._reason_text.setPlainText(
            f"Motivo: {view_model.reason}",
        )
        self._reason_text.moveCursor(
            QTextCursor.MoveOperation.Start,
        )
        self._reason_text.verticalScrollBar().setValue(
            0,
        )
        self._source_label.setText(
            f"Origen: {view_model.source}",
        )
        self._created_at_label.setText(
            f"Fecha: {view_model.created_at_label}",
        )
        self._apply_signal_style(
            css_class=view_model.css_class,
        )
        self._apply_entry_alert(
            view_model=view_model,
        )
        self._append_signal_history(
            view_model=view_model,
        )
        operational_summary = self._operational_summary_presenter.present(
            view_model=view_model,
        )

        self._operational_summary_label.setText(
            operational_summary.text,
        )
        self._apply_operational_summary_style(
            target_direction=operational_summary.target_direction,
        )
        self._update_confirmation_checklist(
            view_model=view_model,
        )
        self._update_session_counter(
            view_model=view_model,
        )
        return (
            self._session_signal_counter.total_count
            > previous_session_total
        )

    def _setup_layout(self) -> None:
        content_widget = QWidget()
        layout = QVBoxLayout()
        self._main_layout = layout

        self._apply_layout_density(
            compact=False,
        )

        layout.addWidget(
            self._status_label,
        )
        layout.addWidget(
            self._error_label,
        )
        layout.addWidget(
            self._capture_note_label,
        )
        layout.addWidget(
            self._entry_alert_label,
        )
        layout.addWidget(
            self._direction_label,
        )
        layout.addWidget(
            self._strength_label,
        )
        layout.addWidget(
            self._operational_summary_label,
        )
        layout.addWidget(
            self._confirmation_checklist_label,
        )
        layout.addWidget(
            self._session_counter_label,
        )
        layout.addWidget(
            self._session_risk_label,
        )
        layout.addWidget(
            self._session_pause_alert_label,
        )
        layout.addWidget(
            self._session_result_label,
        )
        layout.addWidget(
            self._session_result_pause_alert_label,
        )

        result_buttons_layout = QHBoxLayout()
        result_buttons_layout.addWidget(
            self._register_win_button,
        )
        result_buttons_layout.addWidget(
            self._register_loss_button,
        )
        result_buttons_layout.addWidget(
            self._undo_result_button,
        )

        layout.addLayout(
            result_buttons_layout,
        )
        layout.addWidget(
            self._reset_session_button,
        )
        layout.addWidget(
            self._visual_diagnostics_label,
        )
        layout.addWidget(
            self._indicator_diagnostics_label,
        )
        # layout.addWidget(
        #     self._reason_text,
        # )
        layout.addWidget(
            self._source_label,
        )
        layout.addWidget(
            self._created_at_label,
        )
        layout.addWidget(
            self._history_label,
        )
        layout.addWidget(
            self._history_list,
        )
        layout.addWidget(
            self._compact_mode_button,
        )
        layout.addWidget(
            self._reset_view_button,
        )
        layout.addWidget(
            self._voice_toggle_button,
        )
        layout.addWidget(
            self._test_voice_button,
        )
        layout.addWidget(
            self._clear_history_button,
        )
        layout.addWidget(
            self._start_button,
        )
        layout.addWidget(
            self._stop_button,
        )
        layout.addWidget(
            self._run_once_button,
        )

        content_widget.setLayout(
            layout,
        )

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(
            True,
        )
        scroll_area.setWidget(
            content_widget,
        )

        self.setCentralWidget(
            scroll_area,
        )

    def _connect_events(self) -> None:
        self._start_button.clicked.connect(
            self._handle_start_clicked,
        )
        self._stop_button.clicked.connect(
            self._handle_stop_clicked,
        )
        self._run_once_button.clicked.connect(
            self._handle_run_once_clicked,
        )
        self._clear_history_button.clicked.connect(
            self.clear_signal_history,
        )
        self._reset_view_button.clicked.connect(
            self.reset_view,
        )
        self._reset_session_button.clicked.connect(
            self.reset_session,
        )
        self._voice_toggle_button.clicked.connect(
            self._handle_voice_toggle_clicked,
        )
        self._test_voice_button.clicked.connect(
            self._handle_test_voice_clicked,
        )
        self._register_win_button.clicked.connect(
            self.register_session_win,
        )
        self._register_loss_button.clicked.connect(
            self.register_session_loss,
        )
        self._undo_result_button.clicked.connect(
            self.undo_last_session_result,
        )

    def _apply_button_state(
        self,
        is_running: bool,
    ) -> None:

        self._start_button.setEnabled(
            not is_running,
        )
        self._stop_button.setEnabled(
            is_running,
        )
        self._run_once_button.setEnabled(
            not is_running,
        )

    def _handle_voice_toggle_clicked(
        self,
    ) -> None:
        self._set_voice_enabled(
            enabled=self._voice_toggle_button.isChecked(),
        )

    def _handle_test_voice_clicked(
        self,
    ) -> None:
        if not self._voice_enabled:
            return

        if self._on_test_voice_requested is not None:
            self._on_test_voice_requested()

    def _set_voice_enabled(
        self,
        enabled: bool,
        save_preferences: bool = True,
        notify_callback: bool = True,
    ) -> None:
        self._voice_enabled = enabled

        self._voice_toggle_button.setChecked(
            enabled,
        )
        self._voice_toggle_button.setText(
            "Voz activada"
            if enabled
            else "Voz desactivada",
        )
        self._test_voice_button.setEnabled(
            enabled,
        )

        if notify_callback and self._on_voice_enabled_changed is not None:
            self._on_voice_enabled_changed(
                enabled,
            )

        if save_preferences:
            self._save_window_preferences()

    def _apply_signal_style(
        self,
        css_class: str,
    ) -> None:

        if css_class == "signal-call":
            label_style = (
                "font-weight: bold; "
                "color: #0f9d58;"
            )
            reason_style = (
                "border: 1px solid #0f9d58; "
                "background-color: #eefaf3;"
            )

        elif css_class == "signal-put":
            label_style = (
                "font-weight: bold; "
                "color: #d93025;"
            )
            reason_style = (
                "border: 1px solid #d93025; "
                "background-color: #fff0f0;"
            )

        else:
            label_style = (
                "font-weight: bold; "
                "color: #5f6368;"
            )
            reason_style = (
                "border: 1px solid #9aa0a6; "
                "background-color: #f8f9fa;"
            )

        self._direction_label.setStyleSheet(
            label_style,
        )
        self._strength_label.setStyleSheet(
            label_style,
        )
        self._reason_text.setStyleSheet(
            reason_style,
        )

    def _apply_operational_summary_style(
        self,
        target_direction: str,
    ) -> None:
        if target_direction == "CALL":
            self._operational_summary_label.setStyleSheet(
                self.OPERATIONAL_SUMMARY_CALL_STYLE,
            )
            return

        if target_direction == "PUT":
            self._operational_summary_label.setStyleSheet(
                self.OPERATIONAL_SUMMARY_PUT_STYLE,
            )
            return

        self._operational_summary_label.setStyleSheet(
            self.OPERATIONAL_SUMMARY_NEUTRAL_STYLE,
        )

    def _apply_entry_alert(
        self,
        view_model: SignalRecordViewModel,
    ) -> None:
        entry_alert = self._entry_alert_presenter.present(
            view_model=view_model,
        )

        self._entry_alert_label.setText(
            entry_alert.text,
        )
        self._entry_alert_label.setHidden(
            not entry_alert.is_visible,
        )

        if entry_alert.target_direction == "CALL":
            self._entry_alert_label.setStyleSheet(
                self.ENTRY_ALERT_CALL_STYLE,
            )
            return

        if entry_alert.target_direction == "PUT":
            self._entry_alert_label.setStyleSheet(
                self.ENTRY_ALERT_PUT_STYLE,
            )

    def _update_confirmation_checklist(
        self,
        view_model: SignalRecordViewModel,
    ) -> None:
        checklist_view_model = self._confirmation_checklist_presenter.present(
            view_model=view_model,
        )

        self._confirmation_checklist_label.setText(
            checklist_view_model.text,
        )
        self._apply_confirmation_checklist_style(
            target_direction=checklist_view_model.target_direction,
            is_actionable=checklist_view_model.is_actionable,
        )

    def _update_session_counter(
        self,
        view_model: SignalRecordViewModel,
    ) -> None:
        self._session_signal_counter.update(
            view_model=view_model,
        )
        self._refresh_session_counter_label()

    def _refresh_session_counter_label(
        self,
    ) -> None:
        self._session_counter_label.setText(
            self._session_signal_counter.text,
        )
        self._refresh_session_risk_label()
        self._refresh_session_result_ui()

    def _refresh_session_risk_label(
        self,
    ) -> None:
        risk_view_model = self._session_risk_presenter.present(
            total_confirmed_signals=self._session_signal_counter.total_count,
        )

        risk_text = (
            risk_view_model.compact_text
            if self._compact_mode_enabled
            else risk_view_model.text
        )

        self._session_risk_label.setText(
            risk_text,
        )
        self._apply_session_risk_style(
            state=risk_view_model.state,
        )
        self._apply_session_pause_alert(
            state=risk_view_model.state,
        )

    def _apply_session_risk_style(
        self,
        state: str,
    ) -> None:
        if state == SessionRiskPresenter.STATE_LIMIT_REACHED:
            self._session_risk_label.setStyleSheet(
                self.SESSION_RISK_LIMIT_STYLE,
            )
            return

        if state == SessionRiskPresenter.STATE_WARNING:
            self._session_risk_label.setStyleSheet(
                self.SESSION_RISK_WARNING_STYLE,
            )
            return

        self._session_risk_label.setStyleSheet(
            self.SESSION_RISK_OK_STYLE,
        )

    def _apply_session_pause_alert(
        self,
        state: str,
    ) -> None:
        if state == SessionRiskPresenter.STATE_LIMIT_REACHED:
            self._session_pause_alert_label.setText(
                "PAUSA RECOMENDADA\n"
                "Límite de señales alcanzado\n"
                "No buscar más entradas en esta sesión"
            )
            self._session_pause_alert_label.setHidden(
                False,
            )
            return

        self._session_pause_alert_label.setText(
            "",
        )
        self._session_pause_alert_label.setHidden(
            True,
        )

    def _apply_confirmation_checklist_style(
        self,
        target_direction: str,
        is_actionable: bool,
    ) -> None:
        if is_actionable and target_direction == "CALL":
            self._confirmation_checklist_label.setStyleSheet(
                self.CONFIRMATION_CHECKLIST_CALL_STYLE,
            )
            return

        if is_actionable and target_direction == "PUT":
            self._confirmation_checklist_label.setStyleSheet(
                self.CONFIRMATION_CHECKLIST_PUT_STYLE,
            )
            return

        self._confirmation_checklist_label.setStyleSheet(
            self.CONFIRMATION_CHECKLIST_NEUTRAL_STYLE,
        )
    
    def clear_signal_history(self) -> None:
        """
        Limpia el historial visible de señales.

        No elimina el archivo logs/signals.jsonl.
        """

        self._history_list.clear()

    def reset_session(
        self,
    ) -> None:
        """
        Reinicia el estado temporal de señales y resultados.

        Los eventos persistidos en JSONL no se eliminan.
        """

        if self._on_session_reset_requested is not None:
            self._on_session_reset_requested()

        self._session_signal_counter.reset()
        self._session_result_tracker.reset()
        self._refresh_session_counter_label()


    def reset_session_counter(
        self,
    ) -> None:
        """
        Alias conservado por compatibilidad con código y tests anteriores.
        """

        self.reset_session()

    def register_session_win(
        self,
    ) -> None:
        """
        Registra una operación ganada para una señal pendiente.

        El estado visual solo cambia cuando la persistencia fue exitosa.
        """

        if not self._has_pending_session_result():
            return

        if self._on_session_result_registered is not None:
            was_persisted = self._on_session_result_registered(
                SessionResult.WIN,
            )

            if was_persisted is not True:
                return

        self._session_result_tracker.register_win()
        self._refresh_session_result_ui()


    def register_session_loss(
        self,
    ) -> None:
        """
        Registra una operación perdida para una señal pendiente.

        El estado visual solo cambia cuando la persistencia fue exitosa.
        """

        if not self._has_pending_session_result():
            return

        if self._on_session_result_registered is not None:
            was_persisted = self._on_session_result_registered(
                SessionResult.LOSS,
            )

            if was_persisted is not True:
                return

        self._session_result_tracker.register_loss()
        self._refresh_session_result_ui()


    def undo_last_session_result(
        self,
    ) -> None:
        """
        Revierte el último resultado registrado.

        El estado visual solo cambia cuando la reversión fue persistida.
        """

        if self._session_result_tracker.total == 0:
            return

        if self._on_session_result_undone is not None:
            was_reversed = self._on_session_result_undone()

            if was_reversed is not True:
                return

        self._session_result_tracker.undo_last_result()
        self._refresh_session_result_ui()


    def _has_pending_session_result(
        self,
    ) -> bool:
        """
        Indica si existe una señal confirmada que aún no tiene resultado.
        """

        return (
            self._session_result_tracker.total
            < self._session_signal_counter.total_count
        )


    def _refresh_session_result_ui(
        self,
    ) -> None:
        result_view_model = self._session_result_presenter.present(
            snapshot=self._session_result_tracker.snapshot(),
        )

        result_text = (
            result_view_model.compact_text
            if self._compact_mode_enabled
            else result_view_model.text
        )

        self._session_result_label.setText(
            result_text,
        )

        self._session_result_pause_alert_label.setText(
            result_view_model.pause_alert_text,
        )
        self._session_result_pause_alert_label.setHidden(
            not result_view_model.pause_recommended,
        )

        has_pending_result = self._has_pending_session_result()

        self._register_win_button.setEnabled(
            has_pending_result,
        )
        self._register_loss_button.setEnabled(
            has_pending_result,
        )
        self._undo_result_button.setEnabled(
            self._session_result_tracker.total > 0,
        )

    def _append_signal_history(
        self,
        view_model: SignalRecordViewModel,
    ) -> None:

        item_text = (
            f"{view_model.created_at_label} | "
            f"{view_model.direction_label} | "
            f"{view_model.strength_label}"
        )

        self._history_list.insertItem(
            0,
            item_text,
        )

        self._trim_signal_history()

    def _trim_signal_history(
        self,
    ) -> None:

        while self._history_list.count() > self.MAX_SIGNAL_HISTORY_ITEMS:
            self._history_list.takeItem(
                self._history_list.count() - 1,
            )

    def _handle_start_clicked(self) -> None:
        if self._on_start_requested is not None:
            self._on_start_requested()

    def _handle_stop_clicked(self) -> None:
        if self._on_stop_requested is not None:
            self._on_stop_requested()

    def _handle_run_once_clicked(self) -> None:
        if self._on_run_once_requested is not None:
            self._on_run_once_requested()

    def reset_view(self) -> None:
        """
        Restablece la ventana a una vista segura.

        Sale del modo compacto, vuelve a la geometría completa,
        posiciona la ventana dentro del área visible y guarda
        las preferencias limpias.
        """

        self._set_compact_mode(
            enabled=False,
            save_preferences=False,
        )
        self._move_to_safe_position()
        self._save_window_preferences()

    def _toggle_compact_mode(
        self,
    ) -> None:
        self._set_compact_mode(
            enabled=not self._compact_mode_enabled,
        )

    def _set_compact_mode(
        self,
        enabled: bool,
        save_preferences: bool = True,
    ) -> None:
        self._compact_mode_enabled = enabled

        self._status_label.setVisible(
            not enabled,
        )
        self._error_label.setVisible(
            not enabled,
        )
        self._capture_note_label.setVisible(
            not enabled,
        )
        self._visual_diagnostics_label.setVisible(
            not enabled,
        )
        self._indicator_diagnostics_label.setVisible(
            not enabled,
        )
        self._source_label.setVisible(
            not enabled,
        )
        self._created_at_label.setVisible(
            not enabled,
        )
        self._history_label.setVisible(
            not enabled,
        )
        self._history_list.setVisible(
            not enabled,
        )
        self._clear_history_button.setVisible(
            not enabled,
        )
        
        self._entry_alert_label.setVisible(
            not self._entry_alert_label.isHidden(),
        )
        self._direction_label.setVisible(
            True,
        )
        self._strength_label.setVisible(
            True,
        )
        self._operational_summary_label.setVisible(
            True,
        )
        self._confirmation_checklist_label.setVisible(
            True,
        )
        self._session_counter_label.setVisible(
            True,
        )
        self._session_risk_label.setVisible(
            True,
        )
        self._session_pause_alert_label.setVisible(
            not self._session_pause_alert_label.isHidden(),
        )
        self._session_result_label.setVisible(
            True,
        )
        self._register_win_button.setVisible(
            True,
        )
        self._register_loss_button.setVisible(
            True,
        )
        self._undo_result_button.setVisible(
            True,
        )
        self._reset_session_button.setVisible(
            True,
        )
        self._compact_mode_button.setVisible(
            True,
        )
        self._reset_view_button.setVisible(
            True,
        )
        self._start_button.setVisible(
            True,
        )
        self._stop_button.setVisible(
            True,
        )
        self._run_once_button.setVisible(
            True,
        )
        self._voice_toggle_button.setVisible(
            True,
        )
        self._test_voice_button.setVisible(
            True,
        )

        if enabled:
            self._compact_mode_button.setText(
                "Vista completa",
            )
            self._apply_layout_density(
                compact=True,
            )
            self._apply_compact_geometry()
        else:
            self._compact_mode_button.setText(
                "Modo compacto",
            )
            self._apply_layout_density(
                compact=False,
            )
            self._apply_full_geometry()
        
        self._refresh_session_risk_label()
        self._refresh_session_result_ui()

        if save_preferences:
            self._save_window_preferences()

    def _apply_compact_geometry(
        self,
    ) -> None:
        self.setMinimumSize(
            self.COMPACT_MIN_WIDTH,
            self.COMPACT_MIN_HEIGHT,
        )
        self.resize(
            self.COMPACT_WINDOW_WIDTH,
            self.COMPACT_WINDOW_HEIGHT,
        )
        self._apply_layout_density(
            compact=True,
        )

    def _apply_full_geometry(
        self,
    ) -> None:
        self.setMinimumSize(
            self.FULL_MIN_WIDTH,
            self.FULL_MIN_HEIGHT,
        )
        self.resize(
            self.FULL_WINDOW_WIDTH,
            self.FULL_WINDOW_HEIGHT,
        )
        self._apply_layout_density(
            compact=False,
        )

    def _move_to_safe_position(
        self,
    ) -> None:
        screen = QApplication.primaryScreen()

        if screen is None:
            return

        available_geometry = screen.availableGeometry()

        x = max(
            available_geometry.left(),
            available_geometry.right()
            - self.width()
            - self.SAFE_WINDOW_MARGIN,
        )
        y = max(
            available_geometry.top(),
            available_geometry.top() + self.SAFE_WINDOW_MARGIN,
        )

        self.move(
            x,
            y,
        )

    def _apply_layout_density(
        self,
        compact: bool,
    ) -> None:
        margin = (
            self.COMPACT_LAYOUT_MARGIN
            if compact
            else self.FULL_LAYOUT_MARGIN
        )
        spacing = (
            self.COMPACT_LAYOUT_SPACING
            if compact
            else self.FULL_LAYOUT_SPACING
        )

        self._main_layout.setContentsMargins(
            margin,
            margin,
            margin,
            margin,
        )
        self._main_layout.setSpacing(
            spacing,
        )

    def _save_window_preferences(
        self,
    ) -> None:
        if not self._restore_window_preferences_enabled:
            return

        self._settings.beginGroup(
            self.SETTINGS_GROUP,
        )
        self._settings.setValue(
            self.SETTING_COMPACT_MODE,
            self._compact_mode_enabled,
        )
        self._settings.setValue(
            self.SETTING_X,
            self.x(),
        )
        self._settings.setValue(
            self.SETTING_Y,
            self.y(),
        )
        self._settings.setValue(
            self.SETTING_WIDTH,
            self.width(),
        )
        self._settings.setValue(
            self.SETTING_HEIGHT,
            self.height(),
        )
        self._settings.setValue(
            self.SETTING_VOICE_ENABLED,
            self._voice_enabled,
        )
        self._settings.endGroup()
        self._settings.sync()

    def _restore_window_preferences(
        self,
    ) -> None:
        self._settings.beginGroup(
            self.SETTINGS_GROUP,
        )

        compact_mode = self._settings.value(
            self.SETTING_COMPACT_MODE,
            False,
            type=bool,
        )
        x = self._settings.value(
            self.SETTING_X,
            None,
            type=int,
        )
        y = self._settings.value(
            self.SETTING_Y,
            None,
            type=int,
        )
        width = self._settings.value(
            self.SETTING_WIDTH,
            None,
            type=int,
        )
        height = self._settings.value(
            self.SETTING_HEIGHT,
            None,
            type=int,
        )
        voice_enabled = self._settings.value(
            self.SETTING_VOICE_ENABLED,
            True,
            type=bool,
        )

        self._settings.endGroup()

        self._set_voice_enabled(
            enabled=voice_enabled,
            save_preferences=False,
            notify_callback=True,
        )

        self._set_compact_mode(
            enabled=compact_mode,
            save_preferences=False,
        )

        if width is not None and height is not None:
            self.resize(
                width,
                height,
            )

        if x is not None and y is not None:
            self.move(
                x,
                y,
            )

    def closeEvent(
        self,
        event,
    ) -> None:
        self._save_window_preferences()
        super().closeEvent(
            event,
        )