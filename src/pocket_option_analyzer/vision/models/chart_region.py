from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ChartRegion:
    """
    Representa una región rectangular dentro de una imagen.

    Las coordenadas x e y son relativas al origen superior izquierdo
    de la imagen, no coordenadas absolutas de la pantalla.
    """

    x: int

    y: int

    width: int

    height: int

    @property
    def right(
        self,
    ) -> int:
        """
        Devuelve el límite horizontal exclusivo de la región.
        """

        return self.x + self.width

    @property
    def bottom(
        self,
    ) -> int:
        """
        Devuelve el límite vertical exclusivo de la región.
        """

        return self.y + self.height

    @property
    def area(
        self,
    ) -> int:
        """
        Devuelve el área matemática de la región.
        """

        return self.width * self.height

    @property
    def has_positive_area(
        self,
    ) -> bool:
        """
        Indica si ambas dimensiones son estrictamente positivas.
        """

        return self.width > 0 and self.height > 0

    def fits_within(
        self,
        *,
        image_width: int,
        image_height: int,
    ) -> bool:
        """
        Comprueba que la región esté completamente dentro de una imagen.
        """

        if image_width <= 0 or image_height <= 0:
            return False

        return (
            self.x >= 0
            and self.y >= 0
            and self.has_positive_area
            and self.right <= image_width
            and self.bottom <= image_height
        )
