from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CurrentVisualPrice:
    """
    Posición visual del precio actual dentro del ROI del gráfico.

    Este modelo representa una coordenada visual, no un precio monetario.

    ``normalized_roi_y`` utiliza el convenio:

    - 1.0 = parte superior del ROI
    - 0.0 = parte inferior del ROI

    La normalización facilita la observación y comparación diagnóstica,
    pero por sí sola no garantiza comparabilidad entre frames si el
    gráfico cambia su escala vertical.
    """

    roi_y: float
    normalized_roi_y: float
    roi_width: int
    roi_height: int
    source: str
    confidence: float | None = None

    def __post_init__(self) -> None:
        if self.roi_width <= 0:
            raise ValueError("roi_width debe ser mayor que cero.")

        if self.roi_height <= 1:
            raise ValueError("roi_height debe ser mayor que uno.")

        if not 0.0 <= self.roi_y <= self.roi_height - 1:
            raise ValueError(
                "roi_y debe encontrarse dentro de los límites verticales del ROI."
            )

        if not 0.0 <= self.normalized_roi_y <= 1.0:
            raise ValueError(
                "normalized_roi_y debe estar entre 0.0 y 1.0."
            )

        if not self.source:
            raise ValueError("source no puede estar vacío.")

        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                "confidence debe estar entre 0.0 y 1.0."
            )