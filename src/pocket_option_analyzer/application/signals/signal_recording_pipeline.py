from __future__ import annotations

from datetime import datetime

import numpy as np

from pocket_option_analyzer.application.signals.contracts import (
    SignalRecordWriter,
)
from pocket_option_analyzer.application.signals.signal_recorder import (
    SignalRecorder,
)
from pocket_option_analyzer.application.signals.strategy_signal_analysis_pipeline import (
    StrategySignalAnalysisPipeline,
)
from pocket_option_analyzer.domain.indicators import IndicatorSnapshot
from pocket_option_analyzer.domain.signals import SignalRecord


class SignalRecordingPipeline:
    """
    Pipeline de aplicación que analiza el gráfico, genera una señal,
    la registra en memoria y opcionalmente la persiste en disco.

    No ejecuta operaciones.
    No interactúa con Pocket Option.
    Solo analiza, genera y registra señales informativas.
    """

    def __init__(
        self,
        analysis_pipeline: StrategySignalAnalysisPipeline,
        recorder: SignalRecorder,
        record_writer: SignalRecordWriter | None = None,
    ) -> None:
        self._analysis_pipeline = analysis_pipeline
        self._recorder = recorder
        self._record_writer = record_writer

    def analyze_and_record(
        self,
        image: np.ndarray,
        indicators: IndicatorSnapshot,
        created_at: datetime | None = None,
        source: str = "strategy_signal_analysis",
    ) -> SignalRecord:
        """
        Analiza imagen + indicadores, genera una señal,
        la registra en memoria y, si existe writer, la persiste.
        """

        signal = self._analysis_pipeline.analyze(
            image=image,
            indicators=indicators,
        )

        record = self._recorder.record(
            signal=signal,
            created_at=created_at,
            source=source,
        )

        if self._record_writer is not None:
            self._record_writer.write(record)

        return record
