from __future__ import annotations

from collections.abc import Callable

from PySide6.QtGui import QTextOption
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QPushButton,
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
            420,
        )

        self._status_label = QLabel(
            "Estado: detenido",
        )
        self._error_label = QLabel(
            "Error: -",
        )
        self._direction_label = QLabel(
            "Señal: SIN SEÑAL",
        )
        self._strength_label = QLabel(
            "Fuerza: NINGUNA",
        )

        self._reason_text = QTextEdit()
        self._reason_text.setReadOnly(
            True,
        )
        self._reason_text.setPlainText(
            "Motivo: -",
        )
        self._reason_text.setFixedHeight(
            100,
        )
        self._reason_text.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
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
    def reason_style(self) -> str:
        return self._reason_text.styleSheet()

    @property
    def start_button_enabled(self) -> bool:
        return self._start_button.isEnabled()

    @property
    def stop_button_enabled(self) -> bool:
        return self._stop_button.isEnabled()

    @property
    def run_once_button_enabled(self) -> bool:
        return self._run_once_button.isEnabled()

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
        self._reason_text.setPlainText(
            f"Motivo: {view_model.reason}",
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

    def _setup_layout(self) -> None:
        central_widget = QWidget()
        layout = QVBoxLayout()

        layout.addWidget(
            self._status_label,
        )
        layout.addWidget(
            self._error_label,
        )
        layout.addWidget(
            self._direction_label,
        )
        layout.addWidget(
            self._strength_label,
        )
        layout.addWidget(
            self._reason_text,
        )
        layout.addWidget(
            self._source_label,
        )
        layout.addWidget(
            self._created_at_label,
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

        central_widget.setLayout(
            layout,
        )

        self.setCentralWidget(
            central_widget,
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

    def _handle_start_clicked(self) -> None:
        if self._on_start_requested is not None:
            self._on_start_requested()

    def _handle_stop_clicked(self) -> None:
        if self._on_stop_requested is not None:
            self._on_stop_requested()

    def _handle_run_once_clicked(self) -> None:
        if self._on_run_once_requested is not None:
            self._on_run_once_requested()