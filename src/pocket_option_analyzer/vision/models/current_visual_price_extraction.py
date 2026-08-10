from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .current_visual_price import CurrentVisualPrice


class CurrentVisualPriceStatus(StrEnum):
    """
    Estado del intento de localizar visualmente el precio actual.

    Estos estados describen únicamente la extracción visual dentro
    del ROI. No representan una señal de trading ni un resultado
    WIN/LOSS.
    """

    OK = "ok"

    INVALID_IMAGE = "invalid_image"

    NO_VISUAL_PRICE_CANDIDATE = "no_visual_price_candidate"

    AMBIGUOUS_VISUAL_PRICE = "ambiguous_visual_price"

    CANDIDATE_OUTSIDE_SAFE_REGION = "candidate_outside_safe_region"

    LOW_CONFIDENCE = "low_confidence"


@dataclass(frozen=True, slots=True)
class CurrentVisualPriceExtraction:
    """
    Resultado diagnosticable de la extracción del precio visual actual.

    ``price`` solamente está disponible cuando se ha localizado un
    candidato suficientemente fiable.

    Los demás campos permiten auditar por qué un frame fue aceptado
    o rechazado sin depender del detector estructural de velas.
    """

    price: CurrentVisualPrice | None

    status: CurrentVisualPriceStatus

    candidate_count: int = 0

    selected_x: float | None = None

    selected_y: float | None = None

    confidence: float | None = None

    diagnostic: str | None = None

    @property
    def is_available(
        self,
    ) -> bool:
        """
        Indica si existe un precio visual utilizable.
        """

        return (
            self.status is CurrentVisualPriceStatus.OK
            and self.price is not None
        )