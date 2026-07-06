from __future__ import annotations

import numpy as np

from pocket_option_analyzer.vision.models import CandleCandidate
from pocket_option_analyzer.vision.services.binary_mask_builder import BinaryMaskBuilder
from pocket_option_analyzer.vision.services.candle_segmenter import CandleSegmenter
from pocket_option_analyzer.vision.services.candle_filter import CandleFilter


class CandleDetectionPipeline:
    """
    Pipeline encargado de detectar candidatos a velas.
    """

    def __init__(
        self,
        mask_builder: BinaryMaskBuilder,
        segmenter: CandleSegmenter,
        candle_filter: CandleFilter,
    ) -> None:
        self._mask_builder = mask_builder
        self._segmenter = segmenter
        self._filter = candle_filter

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

        return self._filter.filter(candidates)