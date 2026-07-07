from __future__ import annotations

from datetime import datetime

import numpy as np

from pocket_option_analyzer.application.signals.contracts import (
    SignalRecordWriter,
)
from pocket_option_analyzer.application.signals.signal_recorder import (
    SignalRecorder,
)
from pocket_option_analyzer.application.signals.visual_strategy_signal_analysis_pipeline import (
    VisualStrategySignalAnalysisPipeline,
)
from pocket_option_analyzer.domain.signals import SignalRecord


class VisualSignalRecordingPipeline:
    """
    Pipeline de aplicación que analiza visualmente una imagen,
    genera una señal y la registra en memoria/disco.

    No requiere indicadores externos.
    No ejecuta operaciones.
    No interactúa con Pocket Option.
    Solo analiza, genera y registra señales informativas.
    """

    def __init__(
        self,
        analysis_pipeline: VisualStrategySignalAnalysisPipeline,
        recorder: SignalRecorder,
        record_writer: SignalRecordWriter | None = None,
    ) -> None:
        self._analysis_pipeline = analysis_pipeline
        self._recorder = recorder
        self._record_writer = record_writer

    def analyze_and_record(
        self,
        image: np.ndarray,
        created_at: datetime | None = None,
        source: str = "visual_strategy_signal_analysis",
    ) -> SignalRecord:
        """
        Analiza una imagen, genera una señal visual y la registra.
        """

        signal = self._analysis_pipeline.analyze(
            image=image,
        )

        record = self._recorder.record(
            signal=signal,
            created_at=created_at,
            source=source,
        )

        if self._record_writer is not None:
            self._record_writer.write(record)

        return record