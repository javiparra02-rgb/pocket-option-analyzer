from __future__ import annotations

import numpy as np

from pocket_option_analyzer.vision.models.candle_candidate import (
    CandleCandidate,
)
from pocket_option_analyzer.vision.models.candle_detection_trace import (
    CandleCandidateDecision,
    CandleCandidateTrace,
    CandleDetectionResult,
    CandleDetectionTrace,
    CandleFilterResult,
)
from pocket_option_analyzer.vision.models.candle_filter_diagnostics import (
    CandleFilterDiagnostics,
)
from pocket_option_analyzer.vision.services.binary_mask_builder import (
    BinaryMaskBuilder,
)
from pocket_option_analyzer.vision.services.candle_color_detector import (
    CandleColorDetector,
)
from pocket_option_analyzer.vision.services.candle_filter import (
    CandleFilter,
)
from pocket_option_analyzer.vision.services.candle_geometry_extractor import (
    CandleGeometryExtractor,
)
from pocket_option_analyzer.vision.services.candle_observability_analyzer import (
    CandleObservabilityAnalyzer,
)
from pocket_option_analyzer.vision.services.candle_segmenter import (
    CandleSegmenter,
)


class CandleDetectionPipeline:
    """
    Pipeline encargado de detectar candidatos a velas.

    Este pipeline puede enriquecer cada candidato con el color detectado
    dentro de su región.
    """

    def __init__(
        self,
        mask_builder: BinaryMaskBuilder,
        segmenter: CandleSegmenter,
        candle_filter: CandleFilter,
        color_detector: CandleColorDetector | None = None,
        geometry_extractor: CandleGeometryExtractor | None = None,
        observability_analyzer: CandleObservabilityAnalyzer | None = None,
    ) -> None:
        self._mask_builder = mask_builder
        self._segmenter = segmenter
        self._filter = candle_filter
        self._color_detector = color_detector
        self._geometry_extractor = geometry_extractor
        self._observability_analyzer = (
            observability_analyzer or CandleObservabilityAnalyzer()
        )

    @property
    def last_filter_diagnostics(
        self,
    ) -> CandleFilterDiagnostics | None:
        """
        Diagnóstico producido por CandleFilter en la última detección.
        """

        return self._filter.last_diagnostics

    def detect(
        self,
        image: np.ndarray,
    ) -> list[CandleCandidate]:
        """
        Detecta todas las posibles velas presentes
        en una imagen del gráfico.
        """

        return list(self.detect_with_trace(image).candidates)

    def detect_with_trace(
        self,
        image: np.ndarray,
    ) -> CandleDetectionResult:
        """Detecta candidatos y genera su traza durante la misma pasada."""

        mask = self._mask_builder.build(image)

        candidates = self._segmenter.segment(mask)
        candidate_ids = tuple(
            f"candidate_{index:03d}" for index in range(len(candidates))
        )

        colored_candidates = self._assign_colors(
            image=image,
            candidates=candidates,
        )

        filter_result = self._filter_with_trace(
            candidates=colored_candidates,
            candidate_ids=candidate_ids,
        )

        enriched_candidates = self._assign_geometry(
            mask=mask,
            candidates=list(filter_result.candidates),
        )
        return CandleDetectionResult(
            candidates=tuple(enriched_candidates),
            candidate_ids=filter_result.candidate_ids,
            trace=filter_result.trace,
        )

    def _filter_with_trace(
        self,
        *,
        candidates: list[CandleCandidate],
        candidate_ids: tuple[str, ...],
    ) -> CandleFilterResult:
        filter_with_trace = getattr(self._filter, "filter_with_trace", None)
        if callable(filter_with_trace):
            return filter_with_trace(candidates, candidate_ids)

        filtered = tuple(self._filter.filter(candidates))
        source_by_identity = {
            id(candidate): candidate_id
            for candidate_id, candidate in zip(
                candidate_ids,
                candidates,
                strict=True,
            )
        }
        filtered_ids = tuple(
            source_by_identity.get(id(candidate), f"filtered_{index:03d}")
            for index, candidate in enumerate(filtered)
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
                filtered_ids,
                filtered,
                strict=True,
            )
        )
        return CandleFilterResult(
            candidates=filtered,
            candidate_ids=filtered_ids,
            trace=CandleDetectionTrace(
                candidates=trace_candidates,
                merges=(),
                returned_candidate_ids=filtered_ids,
                dominant_width=(
                    self.last_filter_diagnostics.dominant_width
                    if self.last_filter_diagnostics is not None
                    else None
                ),
                maximum_returned_candidates=max(1, len(filtered)),
            ),
        )

    def _assign_colors(
        self,
        image: np.ndarray,
        candidates: list[CandleCandidate],
    ) -> list[CandleCandidate]:

        if self._color_detector is None:
            return candidates

        colored_candidates: list[CandleCandidate] = []

        for candidate in candidates:
            color = self._color_detector.detect(
                image=image,
                candle=candidate,
            )

            colored_candidates.append(
                CandleCandidate(
                    x=candidate.x,
                    y=candidate.y,
                    width=candidate.width,
                    height=candidate.height,
                    area=candidate.area,
                    color=color,
                    geometry=candidate.geometry,
                    observability=candidate.observability,
                )
            )

        return colored_candidates

    def _assign_geometry(
        self,
        mask: np.ndarray,
        candidates: list[CandleCandidate],
    ) -> list[CandleCandidate]:
        """
        Enriquece los candidatos filtrados con cuerpo y mechas.
        """

        if self._geometry_extractor is None:
            return candidates

        enriched_candidates: list[CandleCandidate] = []

        for candidate in candidates:
            geometry = self._geometry_extractor.extract(
                mask=mask,
                candidate=candidate,
            )
            observability = (
                self._observability_analyzer.analyze(
                    geometry=geometry,
                    roi_height=int(mask.shape[0]),
                )
                if geometry is not None
                else None
            )

            enriched_candidates.append(
                CandleCandidate(
                    x=candidate.x,
                    y=candidate.y,
                    width=candidate.width,
                    height=candidate.height,
                    area=candidate.area,
                    color=candidate.color,
                    geometry=geometry,
                    observability=observability,
                )
            )

        return enriched_candidates
