from __future__ import annotations

import numpy as np

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

    def analyze(
        self,
        image: np.ndarray,
    ) -> list[ClassifiedCandle]:
        """
        Analiza una imagen y devuelve velas clasificadas.
        """

        candidates = self._detection_pipeline.detect(image)

        return self._classification_pipeline.classify(candidates)