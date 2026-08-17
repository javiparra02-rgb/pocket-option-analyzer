from __future__ import annotations

import numpy as np

from pocket_option_analyzer.vision.models.candle_detection_trace import (
    CandleAnalysisResult,
    CandleCandidateDecision,
    CandleCandidateTrace,
    CandleDetectionResult,
    CandleDetectionTrace,
)
from pocket_option_analyzer.vision.models.candle_filter_diagnostics import (
    CandleFilterDiagnostics,
)
from pocket_option_analyzer.vision.models.classified_candle import (
    ClassifiedCandle,
)
from pocket_option_analyzer.vision.services.candle_classification_pipeline import (
    CandleClassificationPipeline,
)
from pocket_option_analyzer.vision.services.candle_detection_pipeline import (
    CandleDetectionPipeline,
)


class CandleAnalysisPipeline:
    """
    Pipeline de alto nivel encargado de analizar una imagen del gráfico.

    Combina:
    - detección de candidatos a velas
    - detección de color
    - clasificación bullish / bearish / unknown
    """

    def __init__(
        self,
        detection_pipeline: CandleDetectionPipeline,
        classification_pipeline: CandleClassificationPipeline,
    ) -> None:
        self._detection_pipeline = detection_pipeline
        self._classification_pipeline = classification_pipeline

    @property
    def last_detection_diagnostics(
        self,
    ) -> CandleFilterDiagnostics | None:
        """
        Expone el diagnóstico de detección de la última imagen analizada.
        """

        return self._detection_pipeline.last_filter_diagnostics

    def analyze(
        self,
        image: np.ndarray,
    ) -> list[ClassifiedCandle]:
        """
        Analiza una imagen y devuelve velas clasificadas.
        """

        return list(self.analyze_with_trace(image).candles)

    def analyze_with_trace(
        self,
        image: np.ndarray,
    ) -> CandleAnalysisResult:
        """Clasifica las velas y conserva la traza de esa misma ejecución."""

        detection = self._detect_with_trace(image)
        classified = tuple(
            self._classification_pipeline.classify(list(detection.candidates))
        )
        return CandleAnalysisResult(
            candles=classified,
            candidate_ids=detection.candidate_ids,
            trace=detection.trace,
        )

    def _detect_with_trace(
        self,
        image: np.ndarray,
    ) -> CandleDetectionResult:
        detect_with_trace = getattr(
            self._detection_pipeline,
            "detect_with_trace",
            None,
        )
        if callable(detect_with_trace):
            return detect_with_trace(image)

        candidates = tuple(self._detection_pipeline.detect(image))
        candidate_ids = tuple(
            f"candidate_{index:03d}" for index in range(len(candidates))
        )
        trace_candidates = tuple(
            CandleCandidateTrace(
                candidate_id=candidate_id,
                x=candidate.x,
                y=candidate.y,
                width=candidate.width,
                height=candidate.height,
                area=candidate.area,
                color=candidate.color,
                decisions=(
                    CandleCandidateDecision.SEGMENTED,
                    CandleCandidateDecision.RETURNED,
                ),
            )
            for candidate_id, candidate in zip(
                candidate_ids,
                candidates,
                strict=True,
            )
        )
        diagnostics = self.last_detection_diagnostics
        return CandleDetectionResult(
            candidates=candidates,
            candidate_ids=candidate_ids,
            trace=CandleDetectionTrace(
                candidates=trace_candidates,
                merges=(),
                returned_candidate_ids=candidate_ids,
                dominant_width=(
                    diagnostics.dominant_width if diagnostics is not None else None
                ),
                maximum_returned_candidates=max(1, len(candidates)),
            ),
        )
