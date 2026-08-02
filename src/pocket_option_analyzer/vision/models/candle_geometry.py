from __future__ import annotations

from dataclasses import dataclass


@dataclass(
    frozen=True,
    slots=True,
)
class CandleGeometry:
    """
    Geometría vertical de una vela detectada en pantalla.

    Las coordenadas utilizan el sistema de imagen:

    - menor Y = mayor precio;
    - mayor Y = menor precio.

    Todas las posiciones son absolutas respecto del ROI analizado.
    """

    high_y: int
    body_top_y: int
    body_bottom_y: int
    low_y: int

    def __post_init__(
        self,
    ) -> None:
        coordinates = (
            self.high_y,
            self.body_top_y,
            self.body_bottom_y,
            self.low_y,
        )

        if any(coordinate < 0 for coordinate in coordinates):
            raise ValueError("Las coordenadas de la geometría no pueden ser negativas.")

        if not (self.high_y <= self.body_top_y <= self.body_bottom_y <= self.low_y):
            raise ValueError(
                "La geometría debe respetar el orden "
                "high_y <= body_top_y <= body_bottom_y <= low_y."
            )

    @property
    def upper_wick_height(self) -> int:
        """
        Altura vertical de la mecha superior.
        """

        return self.body_top_y - self.high_y

    @property
    def body_height(self) -> int:
        """
        Cantidad de píxeles verticales ocupados por el cuerpo.
        """

        return self.body_bottom_y - self.body_top_y + 1

    @property
    def lower_wick_height(self) -> int:
        """
        Altura vertical de la mecha inferior.
        """

        return self.low_y - self.body_bottom_y

    @property
    def total_height(self) -> int:
        """
        Cantidad total de píxeles desde máximo hasta mínimo.
        """

        return self.low_y - self.high_y + 1

    @property
    def is_doji_like(self) -> bool:
        """
        Indica si el cuerpo ocupa una sola fila de píxeles.
        """

        return self.body_height == 1
