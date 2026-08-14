from __future__ import annotations

from datetime import UTC, datetime

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
from pocket_option_analyzer.application.signals.visual_strategy_signal_analysis_pipeline import (  # noqa: E501
    VisualStrategySignalAnalysisPipeline,
)
from pocket_option_analyzer.application.strategy import (
    StrategyObservationRecorder,
)
from pocket_option_analyzer.domain.signals import SignalRecord
from pocket_option_analyzer.vision.models import ChartRegion


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
        observation_recorder: StrategyObservationRecorder | None = None,
    ) -> None:
        self._analysis_pipeline = analysis_pipeline
        self._recorder = recorder
        self._record_writer = record_writer
        self._actionable_signal_gate = actionable_signal_gate or ActionableSignalGate()
        self._observation_recorder = observation_recorder

    def analyze_and_record(
        self,
        image: np.ndarray,
        created_at: datetime | None = None,
        source: str = "visual_strategy_signal_analysis",
        price_observation_image: np.ndarray | None = None,
        chart_region: ChartRegion | None = None,
        price_observation_region: ChartRegion | None = None,
    ) -> SignalRecord:
        """
        Analiza una imagen y registra la decisión del gate.
        """

        signal = self._analysis_pipeline.analyze(
            image=image,
            price_observation_image=price_observation_image,
            chart_region=chart_region,
            price_observation_region=price_observation_region,
        )

        resolved_created_at = created_at or datetime.now(
            UTC,
        )

        if self._observation_recorder is not None:
            self._observation_recorder.resolve_due(
                observed_at=resolved_created_at,
                exit_reference=getattr(
                    self._analysis_pipeline,
                    "last_price_reference",
                    None,
                ),
                exit_current_visual_price=getattr(
                    self._analysis_pipeline,
                    "last_current_visual_price",
                    None,
                ),
                exit_visual_price_context=getattr(
                    self._analysis_pipeline,
                    "last_visual_price_comparison_context",
                    None,
                ),
            )
            observation = self._analysis_pipeline.build_last_observation(
                observed_at=resolved_created_at,
            )
            if observation is not None:
                self._observation_recorder.record(observation)

        gate_decision = self._actionable_signal_gate.evaluate(
            signal=signal,
            observed_at=resolved_created_at,
        )

        record = self._recorder.record(
            signal=signal,
            created_at=resolved_created_at,
            source=source,
            disposition=gate_decision.disposition,
            candle_interval_started_at=(gate_decision.interval_key.started_at),
        )

        if self._record_writer is not None:
            self._record_writer.write(
                record,
            )

        return record
