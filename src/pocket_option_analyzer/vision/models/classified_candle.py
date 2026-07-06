from __future__ import annotations

from dataclasses import dataclass

from pocket_option_analyzer.vision.models import (
    CandleCandidate,
    CandleType,
)


@dataclass(frozen=True, slots=True)
class ClassifiedCandle:
    """
    Representa una vela junto con su clasificación.
    """

    candidate: CandleCandidate

    candle_type: CandleType