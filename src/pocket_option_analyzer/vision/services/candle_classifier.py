from __future__ import annotations

from pocket_option_analyzer.vision.models import (
    CandleCandidate,
    CandleType,
    ClassifiedCandle,
)


class CandleClassifier:
    """
    Clasificador básico de velas.

    En esta primera versión únicamente devuelve UNKNOWN.
    La lógica de clasificación se implementará en los siguientes sprints.
    """

    def classify(
        self,
        candle: CandleCandidate,
    ) -> ClassifiedCandle:

        return ClassifiedCandle(
            candidate=candle,
            candle_type=CandleType.UNKNOWN,
        )