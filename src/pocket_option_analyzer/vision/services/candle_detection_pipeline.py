from __future__ import annotations

import numpy as np

from pocket_option_analyzer.vision.models.candle_candidate import (
    CandleCandidate,
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
    ) -> None:
        self._mask_builder = mask_builder
        self._segmenter = segmenter
        self._filter = candle_filter
        self._color_detector = color_detector
        self._geometry_extractor = geometry_extractor

    def detect(
        self,
        image: np.ndarray,
    ) -> list[CandleCandidate]:
        """
        Detecta todas las posibles velas presentes
        en una imagen del gráfico.
        """

        mask = self._mask_builder.build(image)

        candidates = self._segmenter.segment(mask)

        colored_candidates = self._assign_colors(
            image=image,
            candidates=candidates,
        )

        filtered_candidates = self._filter.filter(
            colored_candidates,
        )

        return self._assign_geometry(
            mask=mask,
            candidates=filtered_candidates,
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

            enriched_candidates.append(
                CandleCandidate(
                    x=candidate.x,
                    y=candidate.y,
                    width=candidate.width,
                    height=candidate.height,
                    area=candidate.area,
                    color=candidate.color,
                    geometry=geometry,
                )
            )

        return enriched_candidates
