from __future__ import annotations

from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pocket_option_analyzer.presentation.signals import (
    SignalRecordViewModel,
)


class MainWindow(QMainWindow):
    """
    Ventana principal de la aplicación.

    No ejecuta análisis por sí misma.
    No captura pantalla.
    No interactúa con Pocket Option.

    Solo representa el estado visual inicial de la GUI.
    """

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle(
            "Pocket Option Analyzer",
        )

        self._status_label = QLabel(
            "Estado: detenido",
        )
        self._direction_label = QLabel(
            "Señal: SIN SEÑAL",
        )
        self._strength_label = QLabel(
            "Fuerza: NINGUNA",
        )
        self._reason_label = QLabel(
            "Motivo: -",
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
        self._stop_button = QPushButton(
            "Detener análisis",
        )
        self._run_once_button = QPushButton(
            "Analizar una vez",
        )

        self._setup_layout()

    @property
    def status_text(self) -> str:
        return self._status_label.text()

    @property
    def direction_text(self) -> str:
        return self._direction_label.text()

    @property
    def strength_text(self) -> str:
        return self._strength_label.text()

    @property
    def reason_text(self) -> str:
        return self._reason_label.text()

    @property
    def source_text(self) -> str:
        return self._source_label.text()

    @property
    def created_at_text(self) -> str:
        return self._created_at_label.text()

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
            return

        self._status_label.setText(
            "Estado: detenido",
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
        self._reason_label.setText(
            f"Motivo: {view_model.reason}",
        )
        self._source_label.setText(
            f"Origen: {view_model.source}",
        )
        self._created_at_label.setText(
            f"Fecha: {view_model.created_at_label}",
        )

    def _setup_layout(self) -> None:
        central_widget = QWidget()
        layout = QVBoxLayout()

        layout.addWidget(
            self._status_label,
        )
        layout.addWidget(
            self._direction_label,
        )
        layout.addWidget(
            self._strength_label,
        )
        layout.addWidget(
            self._reason_label,
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