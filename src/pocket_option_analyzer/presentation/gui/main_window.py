from __future__ import annotations

from collections.abc import Callable

from PySide6.QtGui import QTextCursor, QTextOption
from PySide6.QtWidgets import (
    QApplication,
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
    SignalRecordViewModel,
)

WindowAction = Callable[[], None]


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

    def __init__(
        self,
        on_start_requested: WindowAction | None = None,
        on_stop_requested: WindowAction | None = None,
        on_run_once_requested: WindowAction | None = None,
    ) -> None:
        super().__init__()

        self._on_start_requested = on_start_requested
        self._on_stop_requested = on_stop_requested
        self._on_run_once_requested = on_run_once_requested

        self.setWindowTitle(
            "Pocket Option Analyzer",
        )
        self.resize(
            720,
            560,
        )
        self.setMinimumSize(
            520,
            520,
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
        self._operational_summary_label.setStyleSheet(
            "font-weight: bold; color: #1f2937;"
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

        self._compact_mode_enabled = False

        self._setup_layout()
        self._connect_events()
        self._apply_signal_style(
            css_class="signal-neutral",
        )
        self.set_running_state(
            is_running=False,
        )

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
    def visual_diagnostics_text(self) -> str:
        return self._visual_diagnostics_label.text()
    
    @property
    def indicator_diagnostics_text(self) -> str:
        return self._indicator_diagnostics_label.text()
    
    @property
    def compact_mode_button_text(self) -> str:
        return self._compact_mode_button.text()

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
    ) -> None:
        """
        Actualiza la información visible de la última señal.
        """

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
        self._append_signal_history(
            view_model=view_model,
        )
        self._operational_summary_label.setText(
            view_model.operational_summary_label,
        )

    def _setup_layout(self) -> None:
        content_widget = QWidget()
        layout = QVBoxLayout()

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
            self._direction_label,
        )
        layout.addWidget(
            self._strength_label,
        )
        layout.addWidget(
            self._operational_summary_label,
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
    
    def clear_signal_history(self) -> None:
        """
        Limpia el historial visible de señales.

        No elimina el archivo logs/signals.jsonl.
        """

        self._history_list.clear()

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

    def _toggle_compact_mode(
        self,
    ) -> None:
        self._set_compact_mode(
            enabled=not self._compact_mode_enabled,
        )

    def _set_compact_mode(
        self,
        enabled: bool,
    ) -> None:
        self._compact_mode_enabled = enabled

        self._visual_diagnostics_label.setHidden(
            enabled,
        )
        self._indicator_diagnostics_label.setHidden(
            enabled,
        )
        self._source_label.setHidden(
            enabled,
        )
        self._created_at_label.setHidden(
            enabled,
        )
        self._history_label.setHidden(
            enabled,
        )
        self._history_list.setHidden(
            enabled,
        )
        self._clear_history_button.setHidden(
            enabled,
        )

        if enabled:
            self._compact_mode_button.setText(
                "Vista completa",
            )
            return

        self._compact_mode_button.setText(
            "Modo compacto",
        )