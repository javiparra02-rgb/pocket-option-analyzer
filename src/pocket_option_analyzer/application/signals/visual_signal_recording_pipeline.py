from __future__ import annotations

import logging
from datetime import UTC, datetime

import numpy as np

from pocket_option_analyzer.application.evidence import (
    IdentityShadowEvidenceRecorder,
    IdentityShadowFrameEvidence,
    VisualEvidenceAssociation,
    VisualEvidencePhase,
    VisualEvidenceRecorder,
    VisualFrameEvidence,
)
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
    CurrentVisualPriceComparisonContext,
    StrategyObservation,
    StrategyObservationRecorder,
    StrategyObservationResolution,
    StrategyObservationResolutionBatch,
    VisualPriceReference,
    VisualReferenceResolution,
)
from pocket_option_analyzer.domain.signals import SignalRecord
from pocket_option_analyzer.vision.models import (
    ChartRegion,
    CurrentVisualPriceExtraction,
)

logger = logging.getLogger(__name__)


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
        visual_evidence_recorder: VisualEvidenceRecorder | None = None,
        identity_evidence_recorder: IdentityShadowEvidenceRecorder | None = None,
    ) -> None:
        self._analysis_pipeline = analysis_pipeline
        self._recorder = recorder
        self._record_writer = record_writer
        self._actionable_signal_gate = actionable_signal_gate or ActionableSignalGate()
        self._observation_recorder = observation_recorder
        self._visual_evidence_recorder = visual_evidence_recorder
        self._identity_evidence_recorder = identity_evidence_recorder

    def start_session(self, *, session_key: str) -> None:
        """Start session-scoped shadow state in the analysis pipeline."""

        self._analysis_pipeline.start_session(session_key=session_key)
        if self._identity_evidence_recorder is not None:
            try:
                self._identity_evidence_recorder.start_identity_session(
                    session_key=session_key,
                )
            except Exception:  # noqa: BLE001 - diagnostics remain fail-soft.
                logger.exception("Identity evidence session could not be started.")

    def stop_session(self) -> None:
        """Stop session-scoped shadow state after the last frame completes."""

        try:
            self._analysis_pipeline.stop_session()
        finally:
            if self._identity_evidence_recorder is not None:
                try:
                    self._identity_evidence_recorder.stop_identity_session()
                except Exception:  # noqa: BLE001 - shutdown remains fail-soft.
                    logger.exception("Identity evidence session could not be stopped.")

    def analyze_and_record(
        self,
        image: np.ndarray,
        created_at: datetime | None = None,
        source: str = "visual_strategy_signal_analysis",
        price_observation_image: np.ndarray | None = None,
        chart_region: ChartRegion | None = None,
        price_observation_region: ChartRegion | None = None,
        frame_id: int | None = None,
        monotonic_timestamp: float | None = None,
        source_key: str | None = None,
        session_key: str | None = None,
    ) -> SignalRecord:
        """
        Analiza una imagen y registra la decisión del gate.
        """

        resolved_created_at = created_at or datetime.now(
            UTC,
        )

        signal = self._analysis_pipeline.analyze(
            image=image,
            price_observation_image=price_observation_image,
            chart_region=chart_region,
            price_observation_region=price_observation_region,
            frame_id=frame_id,
            frame_timestamp=resolved_created_at,
            monotonic_timestamp=monotonic_timestamp,
            source_key=source_key,
            session_key=session_key,
        )

        evidence_associations: list[VisualEvidenceAssociation] | None = (
            [] if self._visual_evidence_recorder is not None else None
        )
        frame_evidence = self._build_frame_evidence_fail_soft(
            frame_id=frame_id,
            frame_timestamp=resolved_created_at,
            image=image,
            price_observation_image=price_observation_image,
            chart_region=chart_region,
            price_observation_region=price_observation_region,
            source=source,
        )

        if self._observation_recorder is not None:
            exit_reference = getattr(
                self._analysis_pipeline,
                "last_price_reference",
                None,
            )
            exit_current_visual_price = getattr(
                self._analysis_pipeline,
                "last_current_visual_price",
                None,
            )
            exit_visual_price_context = getattr(
                self._analysis_pipeline,
                "last_visual_price_comparison_context",
                None,
            )
            if evidence_associations is None:
                self._observation_recorder.resolve_due(
                    observed_at=resolved_created_at,
                    exit_reference=exit_reference,
                    exit_current_visual_price=exit_current_visual_price,
                    exit_visual_price_context=exit_visual_price_context,
                )
            else:
                self._resolve_due_with_evidence(
                    observed_at=resolved_created_at,
                    exit_reference=exit_reference,
                    exit_current_visual_price=exit_current_visual_price,
                    exit_visual_price_context=exit_visual_price_context,
                    associations=evidence_associations,
                )
            observation = self._analysis_pipeline.build_last_observation(
                observed_at=resolved_created_at,
            )
            if observation is not None:
                accepted = self._observation_recorder.record(observation)
                if accepted and evidence_associations is not None:
                    self._append_entry_association_fail_soft(
                        observation=observation,
                        associations=evidence_associations,
                    )

        self._record_frame_evidence_fail_soft(
            frame_evidence=frame_evidence,
            associations=evidence_associations,
        )
        self._record_identity_evidence_fail_soft(
            frame_id=frame_id,
            frame_timestamp=resolved_created_at,
            monotonic_timestamp=monotonic_timestamp,
            source_key=source_key,
            session_key=session_key,
            image=image,
            chart_region=chart_region,
        )

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

    def _resolve_due_with_evidence(
        self,
        *,
        observed_at: datetime,
        exit_reference: VisualPriceReference | None,
        exit_current_visual_price: CurrentVisualPriceExtraction | None,
        exit_visual_price_context: CurrentVisualPriceComparisonContext | None,
        associations: list[VisualEvidenceAssociation],
    ) -> None:
        if self._observation_recorder is None:
            return
        resolve_with_report = getattr(
            self._observation_recorder,
            "resolve_due_with_report",
            None,
        )
        if callable(resolve_with_report):
            batch = resolve_with_report(
                observed_at=observed_at,
                exit_reference=exit_reference,
                exit_current_visual_price=exit_current_visual_price,
                exit_visual_price_context=exit_visual_price_context,
            )
        else:
            batch = StrategyObservationResolutionBatch(
                resolutions=self._observation_recorder.resolve_due(
                    observed_at=observed_at,
                    exit_reference=exit_reference,
                    exit_current_visual_price=exit_current_visual_price,
                    exit_visual_price_context=exit_visual_price_context,
                ),
                reference_resolutions=(),
            )
        try:
            associations.extend(self._exit_associations(batch))
        except (AttributeError, TypeError, ValueError):
            logger.exception(
                "Visual exit evidence associations could not be constructed."
            )

    @staticmethod
    def _exit_associations(
        batch: StrategyObservationResolutionBatch,
    ) -> tuple[VisualEvidenceAssociation, ...]:
        unique_associations: dict[str, VisualEvidenceAssociation] = {}
        all_resolutions: tuple[
            StrategyObservationResolution | VisualReferenceResolution,
            ...,
        ] = (*batch.resolutions, *batch.reference_resolutions)
        for resolution in all_resolutions:
            association = VisualEvidenceAssociation(
                snapshot_id=resolution.snapshot_id,
                phase=VisualEvidencePhase.EXIT,
                observed_at=resolution.observed_at,
                resolve_at=resolution.resolve_at,
                resolved_at=resolution.resolved_at,
            )
            existing = unique_associations.get(association.snapshot_id)
            if existing is not None and existing != association:
                raise ValueError(
                    "Primary and reference resolutions disagree on snapshot "
                    "timestamps."
                )
            unique_associations.setdefault(
                association.snapshot_id,
                association,
            )
        return tuple(unique_associations.values())

    @staticmethod
    def _append_entry_association_fail_soft(
        *,
        observation: StrategyObservation,
        associations: list[VisualEvidenceAssociation],
    ) -> None:
        try:
            associations.append(
                VisualEvidenceAssociation(
                    snapshot_id=(
                        observation.candle_interval_started_at.isoformat()
                    ),
                    phase=VisualEvidencePhase.ENTRY,
                    observed_at=observation.observed_at,
                    resolve_at=observation.resolve_at,
                    candle_interval_started_at=(
                        observation.candle_interval_started_at
                    ),
                )
            )
        except (AttributeError, TypeError, ValueError):
            logger.exception(
                "Visual entry evidence association could not be constructed."
            )

    def _build_frame_evidence_fail_soft(
        self,
        *,
        frame_id: int | None,
        frame_timestamp: datetime,
        image: np.ndarray,
        price_observation_image: np.ndarray | None,
        chart_region: ChartRegion | None,
        price_observation_region: ChartRegion | None,
        source: str,
    ) -> VisualFrameEvidence | None:
        if self._visual_evidence_recorder is None:
            return None
        if frame_id is None:
            logger.warning(
                "Visual evidence was skipped because the analyzed frame has "
                "no frame_id."
            )
            return None
        try:
            market_analysis = getattr(
                self._analysis_pipeline,
                "last_market_analysis",
                None,
            )
            current_visual_price = getattr(
                self._analysis_pipeline,
                "last_current_visual_price",
                None,
            )
            return VisualFrameEvidence(
                frame_id=frame_id,
                frame_timestamp=frame_timestamp,
                image=image,
                price_observation_image=price_observation_image,
                chart_region=chart_region,
                price_observation_region=price_observation_region,
                source=source,
                market_analysis=market_analysis,
                current_visual_price=current_visual_price,
                visual_price_reference_result=getattr(
                    self._analysis_pipeline,
                    "last_price_reference_result",
                    None,
                ),
                candle_detection_trace=(
                    market_analysis.candle_detection_trace
                    if market_analysis is not None
                    else None
                ),
                current_visual_price_detection_trace=(
                    market_analysis.current_visual_price_detection_trace
                    if market_analysis is not None
                    else None
                ),
            )
        except (AttributeError, TypeError, ValueError):
            logger.exception("Visual frame evidence could not be constructed.")
            return None

    def _record_frame_evidence_fail_soft(
        self,
        *,
        frame_evidence: VisualFrameEvidence | None,
        associations: list[VisualEvidenceAssociation] | None,
    ) -> None:
        if (
            self._visual_evidence_recorder is None
            or frame_evidence is None
            or not associations
        ):
            return
        try:
            self._visual_evidence_recorder.record_frame(
                frame_evidence,
                tuple(associations),
            )
        except Exception:  # noqa: BLE001 - instrumentation must remain fail-soft.
            logger.exception("Visual evidence recorder failed.")

    def _record_identity_evidence_fail_soft(
        self,
        *,
        frame_id: int | None,
        frame_timestamp: datetime,
        monotonic_timestamp: float | None,
        source_key: str | None,
        session_key: str | None,
        image: np.ndarray,
        chart_region: ChartRegion | None,
    ) -> None:
        recorder = self._identity_evidence_recorder
        if recorder is None:
            return
        resolution = getattr(
            self._analysis_pipeline,
            "last_current_candle_identity_resolution",
            None,
        )
        frame_context = getattr(
            self._analysis_pipeline,
            "last_current_candle_identity_frame_context",
            None,
        )
        if resolution is None or frame_context is None:
            return
        if (
            frame_id is None
            or monotonic_timestamp is None
            or source_key is None
            or session_key is None
        ):
            logger.warning(
                "Identity evidence was skipped because runtime metadata is "
                "incomplete."
            )
            return
        try:
            height, width = image.shape[:2]
            evidence = IdentityShadowFrameEvidence(
                frame_id=frame_id,
                frame_timestamp=frame_timestamp,
                monotonic_timestamp=monotonic_timestamp,
                source_key=source_key,
                session_key=session_key,
                roi_width=int(width),
                roi_height=int(height),
                image=image,
                chart_region=chart_region,
                resolution=resolution,
                frame_context=frame_context,
                visual_price_reference_result=getattr(
                    self._analysis_pipeline,
                    "last_price_reference_result",
                    None,
                ),
            )
            recorder.record_identity_shadow(evidence)
        except Exception:  # noqa: BLE001 - instrumentation must remain fail-soft.
            logger.exception("Identity shadow evidence recorder failed.")
