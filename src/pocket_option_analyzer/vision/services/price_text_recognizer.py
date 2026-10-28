from typing import Protocol

import numpy as np
from numpy.typing import NDArray

from pocket_option_analyzer.vision.models.independent_visual_price import OcrReading


class PriceTextRecognitionError(RuntimeError):
    """Sanitized backend reason; do not persist process paths or stderr."""


class PriceTextRecognizer(Protocol):
    """Whole observation image OCR, never cropped around a proposed LABEL."""

    def recognize(
        self, image: NDArray[np.uint8], *, timeout: float, max_words: int
    ) -> OcrReading: ...
