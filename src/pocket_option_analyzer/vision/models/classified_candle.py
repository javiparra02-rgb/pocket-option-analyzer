from __future__ import annotations

from dataclasses import dataclass

from .candle_candidate import CandleCandidate
from .candle_type import CandleType


@dataclass(frozen=True, slots=True)
class ClassifiedCandle:
    """
    Representa una vela junto con su clasificación.
    """

    candidate: CandleCandidate

    candle_type: CandleType
