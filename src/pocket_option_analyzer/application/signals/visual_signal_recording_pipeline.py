from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

from pocket_option_analyzer.application.signals.actionable_signal_gate import (
    ActionableSignalGate,
)
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
    Pipeline que analiza, clasifica y registra señales visuales.

    La primera CALL o PUT de cada vela se acepta.
    Las siguientes conservan su diagnóstico, pero quedan marcadas
    como duplicadas suprimidas.
    """

    def __init__(
        self,
        analysis_pipeline: VisualStrategySignalAnalysisPipeline,
        recorder: SignalRecorder,
        record_writer: SignalRecordWriter | None = None,
        actionable_signal_gate: ActionableSignalGate | None = None,
    ) -> None:
        self._analysis_pipeline = analysis_pipeline
        self._recorder = recorder
        self._record_writer = record_writer
        self._actionable_signal_gate = (
            actionable_signal_gate
            or ActionableSignalGate()
        )

    def analyze_and_record(
        self,
        image: np.ndarray,
        created_at: datetime | None = None,
        source: str = "visual_strategy_signal_analysis",
    ) -> SignalRecord:
        """
        Analiza una imagen y registra la decisión del gate.
        """

        signal = self._analysis_pipeline.analyze(
            image=image,
        )

        resolved_created_at = (
            created_at
            or datetime.now(
                timezone.utc,
            )
        )

        gate_decision = (
            self._actionable_signal_gate.evaluate(
                signal=signal,
                observed_at=resolved_created_at,
            )
        )

        record = self._recorder.record(
            signal=signal,
            created_at=resolved_created_at,
            source=source,
            disposition=gate_decision.disposition,
            candle_interval_started_at=(
                gate_decision.interval_key.started_at
            ),
        )

        if self._record_writer is not None:
            self._record_writer.write(
                record,
            )

        return record