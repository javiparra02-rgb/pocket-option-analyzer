import numpy as np

from pocket_option_analyzer.vision.models import (
    CurrentVisualPriceExtraction,
    CurrentVisualPriceStatus,
)
from pocket_option_analyzer.vision.services import CurrentVisualPriceExtractor


class StubCurrentVisualPriceExtractor:
    def extract(
        self,
        image: np.ndarray,
    ) -> CurrentVisualPriceExtraction:
        return CurrentVisualPriceExtraction(
            price=None,
            status=CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE,
        )


def test_structural_implementation_satisfies_runtime_contract() -> None:
    extractor = StubCurrentVisualPriceExtractor()

    assert isinstance(extractor, CurrentVisualPriceExtractor)

    result = extractor.extract(np.zeros((10, 10, 3), dtype=np.uint8))

    assert isinstance(result, CurrentVisualPriceExtraction)
    assert result.status is CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE
