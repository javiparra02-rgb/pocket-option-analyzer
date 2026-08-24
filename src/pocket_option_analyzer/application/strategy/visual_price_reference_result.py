from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .strategy_observation_outcome import VisualPriceReference


class VisualPriceReferenceStatus(StrEnum):
    """
    Estado del intento de construir una referencia visual de precio.

    Permite distinguir una referencia válida de cada causa concreta
    por la que no fue posible obtenerla.
    """

    OK = "ok"

    LATEST_CANDLE_MISSING = "latest_candle_missing"

    LATEST_GEOMETRY_MISSING = "latest_geometry_missing"

    LATEST_CANDLE_NOT_DIRECTIONAL = "latest_candle_not_directional"

    INSUFFICIENT_ANCHORS = "insufficient_anchors"

    ZERO_ANCHOR_RANGE = "zero_anchor_range"

    CLOSE_OUTSIDE_ANCHOR_RANGE = "close_outside_anchor_range"

    CURRENT_CLOSE_NOT_OBSERVABLE = "current_close_not_observable"


@dataclass(frozen=True, slots=True)
class VisualPriceReferenceResult:
    """
    Resultado diagnosticable de la extracción de referencia visual.

    ``reference`` conserva exactamente la referencia utilizada por los
    resolvers existentes.

    Cuando no existe una referencia fiable, ``status`` explica la causa
    y los campos opcionales permiten auditar la geometría observada.
    """

    reference: VisualPriceReference | None

    status: VisualPriceReferenceStatus

    anchor_count: int = 0

    latest_candle_type: str | None = None

    latest_candidate_x: int | None = None

    latest_candidate_y: int | None = None

    close_roi_y: int | None = None

    anchor_top_roi_y: int | None = None

    anchor_bottom_roi_y: int | None = None

    raw_normalized_close: float | None = None

    @property
    def is_available(
        self,
    ) -> bool:
        """
        Indica si el resultado contiene una referencia utilizable.
        """

        return (
            self.status is VisualPriceReferenceStatus.OK and self.reference is not None
        )
