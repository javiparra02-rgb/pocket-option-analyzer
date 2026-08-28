from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np

from pocket_option_analyzer.vision.models.current_visual_price_search import (
    CurrentVisualPriceSearchConstraints,
    CurrentVisualPriceSearchPlan,
)


@runtime_checkable
class CurrentVisualPriceSearchWindowResolver(Protocol):
    """Construye ventanas semánticas reutilizando una máscara ya calculada."""

    def resolve(
        self,
        *,
        mask: np.ndarray,
        constraints: CurrentVisualPriceSearchConstraints,
    ) -> CurrentVisualPriceSearchPlan: ...
